

import { GoogleGenAI } from "@google/genai";
import { PlacedRoom, StructuralItem } from "../types";

const getClient = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    throw new Error("API Key is missing. Please set process.env.API_KEY.");
  }
  return new GoogleGenAI({ apiKey });
};

const cleanBase64 = (dataUrl: string) => {
    if (dataUrl.includes('base64,')) {
        return dataUrl.split('base64,')[1];
    }
    return dataUrl;
};

export const generateFloorPlanImage = async (
  area: number,
  shape: string,
  rooms: PlacedRoom[],
  structures: StructuralItem[] = [],
  styleName: string,
  useProModel: boolean = false
): Promise<string> => {
  const ai = getClient();
  
  const layoutDescriptions = rooms.map(room => {
    return `- ${room.name}: located at X=${room.x}%, Y=${room.y}%, size ${room.width}% width x ${room.height}% height.`;
  }).join('\n');

  const structureDescriptions = structures.map(s => {
      let desc = '';
      if (s.type === 'door') desc = `Door (swinging) at X=${s.x}%, Y=${s.y}%`;
      if (s.type === 'window') desc = `Window (glazing) at X=${s.x}%, Y=${s.y}%, width ${s.width}%`;
      if (s.type === 'wall') desc = `Partition Wall at X=${s.x}%, Y=${s.y}%, length ${s.width}%`;
      if (s.type === 'cabinet') desc = `Built-in Cabinet/Storage at X=${s.x}%, Y=${s.y}%, size ${s.width}% x ${s.height}%`;
      if (s.type === 'custom') desc = `Custom Area/Furniture at X=${s.x}%, Y=${s.y}%, size ${s.width}% x ${s.height}%`;
      if (s.rotation > 0) desc += `, Rotated ${s.rotation} degrees`;
      return `- ${desc}`;
  }).join('\n');

  const shapeDesc = shape === 'square' ? '1:1 square' : '4:3 rectangle';
  const prompt = `
    Create a professional architectural floor plan line drawing (top-down blueprint).
    Layout Specifications:
    - Total Area: ${area} square meters.
    - Overall Shape: ${shapeDesc}.
    - Interior Style context: ${styleName}.
    
    SPATIAL LAYOUT REQUIREMENTS (Follow Strictly):
    ${layoutDescriptions}

    STRUCTURAL ELEMENTS (Follow Strictly):
    ${structureDescriptions}
    
    CRITICAL RESTRICTIONS (NEGATIVE PROMPT):
    - NO TEXT. DO NOT generate any room names, labels, or letters.
    - NO NUMBERS. DO NOT generate dimensions or area calculations.
    - NO ANNOTATIONS.
    - The output must be PURE GEOMETRY (lines and shapes) only.
    
    Visual Style:
    - Clean black lines on a pure white background.
    - Clear wall thickness and partitions.
    - Indicate door swings and windows clearly matching the structure descriptions.
    - Draw built-in cabinets with crossed lines if specified.
    - Minimalist furniture outlines (e.g., bed, sofa, table) to suggest room function WITHOUT text.
    - High contrast, technical drawing style.
  `;
  const model = useProModel ? 'gemini-3-pro-image-preview' : 'gemini-2.5-flash-image';
  try {
    const response = await ai.models.generateContent({
      model: model,
      contents: { parts: [{ text: prompt }] },
      config: {
        imageConfig: {
            aspectRatio: shape === 'square' ? "1:1" : "4:3",
            ...(useProModel ? { imageSize: '2K' } : {})
        }
      }
    });
    for (const part of response.candidates[0].content.parts) {
      if (part.inlineData) {
        return `data:image/png;base64,${part.inlineData.data}`;
      }
    }
    throw new Error("No image generated");
  } catch (error) {
    console.error("Floor plan generation error:", error);
    throw error;
  }
};

export const generate3DPerspective = async (
  rooms: PlacedRoom[],
  stylePrompt: string,
  floorPlanImage?: string,
  useProModel: boolean = false
): Promise<string> => {
  const ai = getClient();
  const roomNames = rooms.map(r => r.name).join(', ');
  let prompt = `
    Generate a 3D isometric cutaway render of a modern home interior.
    CONTEXT:
    - Style: ${stylePrompt}.
    - Rooms visible: ${roomNames}.
    INSTRUCTION:
    - If a floor plan image is provided, YOU MUST FOLLOW ITS LAYOUT EXACTLY.
    - Build the 3D walls and furniture matching the provided 2D blueprint.
    - Use the specified style for materials and lighting.
    Visuals:
    - Isometric view (cutaway ceiling).
    - Photorealistic lighting.
    - Detailed textures.
    - 45-degree angle.
    - White background studio setting.
  `;
  const parts: any[] = [{ text: prompt }];
  if (floorPlanImage) {
      parts.push({
          inlineData: {
              mimeType: 'image/png',
              data: cleanBase64(floorPlanImage)
          }
      });
  }
  const model = useProModel ? 'gemini-3-pro-image-preview' : 'gemini-2.5-flash-image';
  try {
    const response = await ai.models.generateContent({
      model: model,
      contents: { parts: parts },
      config: {
        imageConfig: {
            aspectRatio: "4:3",
            ...(useProModel ? { imageSize: '2K' } : {})
        }
      }
    });
    for (const part of response.candidates[0].content.parts) {
      if (part.inlineData) {
        return `data:image/png;base64,${part.inlineData.data}`;
      }
    }
    throw new Error("No image generated");
  } catch (error) {
    console.error("3D generation error:", error);
    throw error;
  }
};

export const generatePanoramaView = async (
  roomName: string,
  stylePrompt: string,
  referenceImage?: string,
  useProModel: boolean = false
): Promise<string> => {
  const ai = getClient();
  const prompt = `
    Generate a 360-degree equirectangular panoramic image of a ${roomName}.
    INSTRUCTION:
    - Style: ${stylePrompt}.
    - IMPORTANT: Match the aesthetic, color palette, and furniture style of the attached reference image (if provided).
    - This room belongs to the house shown in the reference.
    Visuals:
    - Photorealistic interior.
    - Seamless left-right.
    - High detail.
    - Ultra-wide angle.
  `;
  const parts: any[] = [{ text: prompt }];
  if (referenceImage) {
      parts.push({
          inlineData: {
              mimeType: 'image/png',
              data: cleanBase64(referenceImage)
          }
      });
  }
  const model = useProModel ? 'gemini-3-pro-image-preview' : 'gemini-2.5-flash-image';
  try {
    const response = await ai.models.generateContent({
      model: model,
      contents: { parts: parts },
      config: {
        imageConfig: {
            aspectRatio: "16:9",
            ...(useProModel ? { imageSize: '2K' } : {})
        }
      }
    });
    for (const part of response.candidates[0].content.parts) {
      if (part.inlineData) {
        return `data:image/png;base64,${part.inlineData.data}`;
      }
    }
    throw new Error("No image generated");
  } catch (error) {
    console.error("Panorama generation error:", error);
    throw error;
  }
};

export const generateDesignCritique = async (
  rooms: PlacedRoom[],
  area: number,
  shape: string
): Promise<string> => {
  const ai = getClient();
  const layoutDesc = rooms.map(r => 
    `${r.name} (Position: ${r.x}%,${r.y}%, Size: ${r.width}%x${r.height}%)`
  ).join(', ');

  const prompt = `
    作為一位專業的室內設計師與風水顧問，請分析以下住宅平面配置圖。
    
    專案資訊：
    - 總面積：${area} 平方公尺
    - 基地形狀：${shape}
    - 房間配置：${layoutDesc}
    
    請提供以下分析（請用繁體中文，條列式）：
    1. **動線分析**：房間之間的連接是否合理？有沒有動線衝突？
    2. **空間利用**：目前的配置是否浪費空間？或是某些房間過小？
    3. **風水建議**：以亞洲觀點，簡單分析入門、廚房、臥室的相對位置是否有明顯禁忌？
    4. **優化建議**：具體建議如何移動房間以獲得更好的居住體驗。
    
    請保持語氣專業、友善且具建設性。
  `;

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: { parts: [{ text: prompt }] },
    });
    return response.text || "無法產生分析結果。";
  } catch (error) {
    console.error("Critique error:", error);
    return "分析服務暫時無法使用，請稍後再試。";
  }
};

export const generateBudgetEstimate = async (
  rooms: PlacedRoom[],
  area: number,
  styleName: string,
  image3D?: string
): Promise<string> => {
  const ai = getClient();
  const roomNames = rooms.map(r => r.name).join(', ');
  
  const prompt = `
    請根據以下房屋設計資料，提供一份粗略的「室內裝修預算估價單」。
    
    房屋資訊：
    - 總坪數：約 ${Math.round(area * 0.3025)} 坪 (${area} m²)
    - 風格：${styleName}
    - 包含空間：${roomNames}
    
    請參考所附的 3D 渲染圖（如果有），分析建材等級（例如地板材質、牆面處理、櫃體多寡）。
    
    請輸出 JSON 格式 (不要 Markdown code block)，包含以下欄位：
    {
      "level": "經濟型 / 舒適型 / 豪華型",
      "total_range": "總價範圍 (例如：150萬 - 200萬 TWD)",
      "breakdown": [
        {"item": "項目名稱 (如：拆除工程)", "cost": "預估費用"},
        ...
      ],
      "advice": "針對此風格的省錢或重點裝修建議 (繁體中文)"
    }
  `;

  const parts: any[] = [{ text: prompt }];
  if (image3D) {
    parts.push({
      inlineData: {
        mimeType: 'image/png',
        data: cleanBase64(image3D)
      }
    });
  }

  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: { parts: parts },
      config: { responseMimeType: "application/json" }
    });
    return response.text || "{}";
  } catch (error) {
    console.error("Budget error:", error);
    return JSON.stringify({ error: "估算失敗" });
  }
};