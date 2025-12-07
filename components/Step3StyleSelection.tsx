
import React, { useEffect, useState } from 'react';
import { Button } from './Button';
import { ARCH_STYLES, PlacedRoom, StructuralItem } from '../types';
import { generateFloorPlanImage } from '../services/geminiService';

interface Props {
  selectedStyle: string;
  setSelectedStyle: (s: string) => void;
  generatedImage: string | null;
  setGeneratedImage: (img: string) => void;
  area: number;
  shape: 'square' | 'rectangle';
  rooms: PlacedRoom[];
  structures: StructuralItem[];
  onNext: () => void;
  onPrev: () => void;
  useProModel: boolean;
  setUseProModel: (val: boolean) => void;
}

export const Step3StyleSelection: React.FC<Props> = ({ 
  selectedStyle, setSelectedStyle, generatedImage, setGeneratedImage, 
  area, shape, rooms, structures, onNext, onPrev, useProModel, setUseProModel
}) => {
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTogglePro = async () => {
    if (!useProModel) {
      // Trying to enable Pro
      try {
        if (window.aistudio && !await window.aistudio.hasSelectedApiKey()) {
           await window.aistudio.openSelectKey();
        }
        // If we get here, user likely selected a key or already had one
        setUseProModel(true);
      } catch (e) {
        console.warn("API Key selection cancelled or failed", e);
        setUseProModel(false);
      }
    } else {
      setUseProModel(false);
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const styleObj = ARCH_STYLES.find(s => s.id === selectedStyle);
      const img = await generateFloorPlanImage(
          area, 
          shape, 
          rooms,
          structures, 
          styleObj?.promptModifier || '',
          useProModel
      );
      setGeneratedImage(img);
    } catch (err) {
      setError("生成失敗。若使用 Pro 模型，請確認您的 API Key 是否有效且有權限。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!generatedImage && selectedStyle) {
      handleGenerate();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); 

  return (
    <div className="space-y-6 animate-fade-in h-full flex flex-col">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-grow">
        
        {/* Style Grid */}
        <div className="lg:col-span-4 bg-white/80 backdrop-blur-sm p-6 rounded-3xl shadow-sm border border-gray-100 flex flex-col h-full overflow-hidden">
          <div className="flex justify-between items-start mb-2">
            <div>
                <h3 className="text-xl font-bold text-gray-800">3. 選擇設計風格</h3>
                <p className="text-gray-500 text-sm">AI 將根據選擇繪製風格藍圖</p>
            </div>
          </div>
          
          <div className="mb-4 bg-gradient-to-r from-purple-50 to-blue-50 p-3 rounded-xl border border-purple-100">
             <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-purple-800 flex items-center gap-1">
                   ✨ 啟用 Gemini 3 Pro <span className="hidden sm:inline">高畫質模式</span>
                </span>
                <button 
                  onClick={handleTogglePro}
                  className={`w-10 h-6 rounded-full p-1 transition-colors duration-300 ${useProModel ? 'bg-purple-600' : 'bg-gray-300'}`}
                >
                  <div className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-300 ${useProModel ? 'translate-x-4' : 'translate-x-0'}`}></div>
                </button>
             </div>
             {useProModel && <p className="text-[10px] text-purple-600 mt-1">將使用您的個人 API Key 生成 2K 高解析度圖片。</p>}
          </div>
          
          <div className="grid grid-cols-1 gap-3 overflow-y-auto pr-2 custom-scrollbar flex-grow">
            {ARCH_STYLES.map(style => (
              <button
                key={style.id}
                onClick={() => setSelectedStyle(style.id)}
                className={`text-left p-4 rounded-xl border-2 transition-all duration-200 group relative overflow-hidden ${selectedStyle === style.id ? 'border-brand-500 bg-brand-50' : 'border-gray-100 hover:border-brand-200 hover:bg-white'}`}
              >
                <div className={`absolute top-0 right-0 p-1 rounded-bl-lg bg-brand-500 text-white text-xs transition-opacity ${selectedStyle === style.id ? 'opacity-100' : 'opacity-0'}`}>
                  Selected
                </div>
                <div className="font-bold text-gray-800 mb-1 relative z-10">{style.name.split(' ')[0]}</div>
                <p className="text-xs text-gray-500 relative z-10 line-clamp-2">{style.description}</p>
              </button>
            ))}
          </div>
          
          <div className="pt-4 mt-2 border-t border-gray-100">
             <Button 
                onClick={handleGenerate} 
                isLoading={loading} 
                className={`w-full text-white ${useProModel ? 'bg-purple-600 hover:bg-purple-700' : 'bg-brand-600 hover:bg-brand-700'}`}
             >
               {generatedImage ? '↻ 重新生成' : '生成預覽'}
             </Button>
          </div>
        </div>

        {/* Preview Area */}
        <div className="lg:col-span-8 bg-gray-900 rounded-3xl shadow-2xl overflow-hidden relative flex items-center justify-center group min-h-[400px] border border-gray-800">
          
          {/* Decorative grid on dark bg */}
          <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(#ffffff 1px, transparent 1px)', backgroundSize: '30px 30px' }}></div>

          {loading && (
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-20 flex flex-col items-center justify-center text-white">
              <div className={`w-16 h-16 border-t-4 border-r-transparent rounded-full animate-spin mb-6 ${useProModel ? 'border-purple-500' : 'border-brand-500'}`}></div>
              <p className="font-light tracking-widest uppercase text-sm animate-pulse">Rendering Blueprint...</p>
              {useProModel && <p className="text-xs text-purple-300 mt-2">Using Gemini 3 Pro</p>}
            </div>
          )}

          {error && (
             <div className="relative z-30 text-red-400 bg-red-950/80 backdrop-blur p-8 rounded-2xl text-center border border-red-500/30">
                <p className="font-bold text-lg mb-2">生成錯誤</p>
                <p className="text-sm opacity-80">{error}</p>
                <Button onClick={handleGenerate} variant="outline" className="mt-6 border-red-500 text-red-400 hover:bg-red-500 hover:text-white">重試</Button>
             </div>
          )}

          {!generatedImage && !loading && !error && (
            <div className="text-gray-600 flex flex-col items-center">
              <span className="text-6xl mb-4 opacity-20">📐</span>
              <p className="font-mono text-sm opacity-50">PREVIEW AREA</p>
            </div>
          )}

          {generatedImage && !loading && (
            <div className="relative w-full h-full p-8 flex items-center justify-center">
              <img 
                src={generatedImage} 
                alt="AI Generated Floor Plan" 
                className="max-w-full max-h-full object-contain shadow-2xl rounded-lg bg-white"
              />
              <div className={`absolute top-6 left-6 backdrop-blur text-white text-xs px-3 py-1.5 rounded-full border border-white/10 font-mono ${useProModel ? 'bg-purple-900/80 ring-1 ring-purple-500' : 'bg-black/70'}`}>
                {useProModel ? '✨ GEMINI_3_PRO' : 'GENERATED_BY_GEMINI'}
              </div>
            </div>
          )}
        </div>

      </div>

      <div className="flex justify-between items-center bg-white/50 backdrop-blur px-6 py-4 rounded-2xl border border-gray-100">
        <Button onClick={onPrev} variant="outline" className="border-gray-300 text-gray-500">
          ← 修改配置
        </Button>
        <Button onClick={onNext} disabled={!generatedImage} className="bg-gray-900 text-white hover:bg-black shadow-lg">
          確認設計，建立 3D 模型 →
        </Button>
      </div>
    </div>
  );
};
