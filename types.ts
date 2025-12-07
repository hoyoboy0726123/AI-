

export interface RoomType {
  id: string;
  name: string;
  color: string;
  minSize: number;
  icon: string;
}

export interface PlacedRoom {
  id: string;
  typeId: string;
  name: string;
  color: string;
  width: number; // Percentage width (0-100)
  height: number; // Percentage height (0-100)
  x: number; // Percentage X position (0-100)
  y: number; // Percentage Y position (0-100)
}

export type StructureType = 'wall' | 'window' | 'door' | 'cabinet' | 'custom';

export interface StructuralItem {
  id: string;
  type: StructureType;
  x: number; // Percentage
  y: number; // Percentage
  width: number; // Percentage (Length)
  height: number; // Percentage (Thickness, usually fixed or small)
  rotation: number; // 0, 90, 180, 270
}

export interface ArchitecturalStyle {
  id: string;
  name: string;
  description: string;
  promptModifier: string;
}

export interface ProjectData {
  version: number;
  timestamp: string;
  currentStep: number;
  area: number;
  shape: 'square' | 'rectangle';
  rooms: PlacedRoom[];
  structures: StructuralItem[];
  selectedStyle: string;
  generatedPlanImage: string | null;
  useProModel: boolean;
}

export const ROOM_TYPES: RoomType[] = [
  { id: 'bedroom', name: '臥室', color: 'bg-orange-100 border-orange-300 text-orange-800', minSize: 15, icon: '🛏️' },
  { id: 'bathroom', name: '浴室', color: 'bg-cyan-100 border-cyan-300 text-cyan-800', minSize: 8, icon: '🚿' },
  { id: 'kitchen', name: '廚房', color: 'bg-red-100 border-red-300 text-red-800', minSize: 10, icon: '🍳' },
  { id: 'living', name: '客廳', color: 'bg-blue-100 border-blue-300 text-blue-800', minSize: 20, icon: '🛋️' },
  { id: 'dining', name: '餐廳', color: 'bg-yellow-100 border-yellow-300 text-yellow-800', minSize: 12, icon: '🍽️' },
  { id: 'study', name: '書房', color: 'bg-green-100 border-green-300 text-green-800', minSize: 10, icon: '📚' },
  { id: 'balcony', name: '陽台', color: 'bg-teal-100 border-teal-300 text-teal-800', minSize: 5, icon: '🌿' },
  { id: 'foyer', name: '玄關', color: 'bg-gray-100 border-gray-300 text-gray-800', minSize: 3, icon: '🚪' },
];

export const ARCH_STYLES: ArchitecturalStyle[] = [
  { id: 'modern_minimalist', name: '現代簡約 (Modern Minimalist)', description: '乾淨線條，中性色調，注重功能性', promptModifier: 'Modern Minimalist style, clean lines, neutral colors, functional, decluttered, sleek' },
  { id: 'scandinavian', name: '北歐風格 (Scandinavian)', description: '明亮，木質元素，舒適溫馨', promptModifier: 'Scandinavian style, bright, airy, light wood textures, cozy, hygge, minimalist yet warm' },
  { id: 'industrial', name: '工業風格 (Industrial)', description: '裸露磚牆，金屬元素，粗獷質感', promptModifier: 'Industrial loft style, exposed brick, concrete, metal pipes, raw textures, vintage lighting' },
  { id: 'japanese_zen', name: '日式無印 (Japanese Zen)', description: '原木，榻榻米，寧靜和諧', promptModifier: 'Japanese Zen style, muji aesthetic, light wood, tatami mats, peaceful, harmonious, natural light' },
  { id: 'modern_luxury', name: '現代奢華 (Modern Luxury)', description: '大理石，金色點綴，高級質感', promptModifier: 'Modern Luxury style, marble floors, gold accents, high-end furniture, dramatic lighting, sophisticated' },
  { id: 'neoclassical', name: '新古典 (Neo-Classical)', description: '優雅裝飾，對稱佈局，經典氛圍', promptModifier: 'Neo-Classical style, elegant moldings, symmetrical layout, rich fabrics, timeless, sophisticated' },
];

declare global {
  interface Window {
    html2pdf?: any;
    // aistudio is defined in the environment types
  }
}