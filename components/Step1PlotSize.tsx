import React from 'react';
import { Button } from './Button';

interface Props {
  area: number;
  setArea: (a: number) => void;
  shape: 'square' | 'rectangle';
  setShape: (s: 'square' | 'rectangle') => void;
  onNext: () => void;
}

export const Step1PlotSize: React.FC<Props> = ({ area, setArea, shape, setShape, onNext }) => {
  return (
    <div className="space-y-8 animate-fade-in max-w-4xl mx-auto">
      <div className="bg-white/80 backdrop-blur-sm p-8 rounded-3xl shadow-sm border border-gray-100/50">
        <div className="text-center mb-10">
          <h3 className="text-2xl font-bold text-gray-800 mb-2">設定地基規格</h3>
          <p className="text-gray-500">第一步：定義您的建築範圍與形狀</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          {/* Shape Selection */}
          <div className="space-y-4">
            <label className="text-sm font-semibold text-gray-500 uppercase tracking-wider">選擇形狀</label>
            <div className="grid grid-cols-2 gap-4">
              <button
                onClick={() => setShape('square')}
                className={`group relative p-6 border-2 rounded-2xl flex flex-col items-center gap-4 transition-all duration-300 ${shape === 'square' ? 'border-brand-500 bg-brand-50 shadow-md ring-2 ring-brand-200 ring-offset-2' : 'border-gray-100 hover:border-gray-200 hover:bg-white'}`}
              >
                <div className={`w-16 h-16 border-2 rounded-lg transition-colors ${shape === 'square' ? 'border-brand-500 bg-brand-200' : 'border-gray-300 bg-gray-50'}`} style={{ aspectRatio: '1/1' }}></div>
                <span className={`font-medium ${shape === 'square' ? 'text-brand-600' : 'text-gray-400'}`}>正方形 (1:1)</span>
              </button>
              
              <button
                onClick={() => setShape('rectangle')}
                className={`group relative p-6 border-2 rounded-2xl flex flex-col items-center gap-4 transition-all duration-300 ${shape === 'rectangle' ? 'border-brand-500 bg-brand-50 shadow-md ring-2 ring-brand-200 ring-offset-2' : 'border-gray-100 hover:border-gray-200 hover:bg-white'}`}
              >
                <div className={`w-20 h-14 border-2 rounded-lg transition-colors ${shape === 'rectangle' ? 'border-brand-500 bg-brand-200' : 'border-gray-300 bg-gray-50'}`} style={{ aspectRatio: '4/3' }}></div>
                <span className={`font-medium ${shape === 'rectangle' ? 'text-brand-600' : 'text-gray-400'}`}>長方形 (4:3)</span>
              </button>
            </div>
          </div>

          {/* Area Slider */}
          <div className="space-y-6">
             <div className="flex justify-between items-end">
                <label className="text-sm font-semibold text-gray-500 uppercase tracking-wider">總坪數面積</label>
                <div className="text-right">
                  <span className="text-5xl font-bold text-brand-600 tracking-tighter">{area}</span>
                  <span className="text-gray-400 ml-1 font-medium">m²</span>
                </div>
             </div>
             
             <div className="relative pt-6 pb-2">
                <input 
                  type="range" 
                  min="30" 
                  max="300" 
                  step="5"
                  value={area}
                  onChange={(e) => setArea(Number(e.target.value))}
                  className="w-full h-3 bg-gray-100 rounded-full appearance-none cursor-pointer accent-brand-500 hover:accent-brand-600 transition-all"
                />
                <div className="flex justify-between text-xs font-medium text-gray-400 mt-3">
                  <span className="bg-gray-100 px-2 py-1 rounded">小公寓 30m²</span>
                  <span className="bg-gray-100 px-2 py-1 rounded">豪華別墅 300m²</span>
                </div>
             </div>
          </div>
        </div>
      </div>

      <div className="flex justify-center">
        <Button onClick={onNext} className="w-full md:w-auto px-12 py-4 text-lg shadow-xl shadow-brand-500/20 rounded-full">
          確認並繼續 ➜
        </Button>
      </div>
    </div>
  );
};