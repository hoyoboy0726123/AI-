
import React, { useEffect, useState, useRef } from 'react';
import { Button } from './Button';
import { ARCH_STYLES, PlacedRoom, StructuralItem } from '../types';
import { generate3DPerspective, generatePanoramaView, generateBudgetEstimate } from '../services/geminiService';
import { PanoramaViewer } from './PanoramaViewer';

interface Props {
  rooms: PlacedRoom[];
  structures: StructuralItem[];
  selectedStyle: string;
  floorPlanImage: string | null;
  onRestart: () => void;
  onBack: () => void;
  useProModel: boolean;
  setUseProModel: (val: boolean) => void;
}

interface Label {
  id: string;
  type: 'text' | 'block';
  text?: string;
  x: number;
  y: number;
  width?: number; // for block type
  height?: number; // for block type
}

export const Step4FinalResult: React.FC<Props> = ({ 
  rooms, structures, selectedStyle, floorPlanImage, onRestart, onBack, useProModel, setUseProModel 
}) => {
  const [activeTab, setActiveTab] = useState<'3d' | 'blueprint'>('3d');
  
  // 3D & Panorama State
  const [image3D, setImage3D] = useState<string | null>(null);
  const [loading3D, setLoading3D] = useState(false);
  const [panoramaImage, setPanoramaImage] = useState<string | null>(null);
  const [loadingPanorama, setLoadingPanorama] = useState(false);
  const [showPanoramaModal, setShowPanoramaModal] = useState(false);
  const [selectedRoomForPanorama, setSelectedRoomForPanorama] = useState<string>('');

  // New Features State
  const [showLightbox, setShowLightbox] = useState(false);
  const [showBudgetModal, setShowBudgetModal] = useState(false);
  const [budgetLoading, setBudgetLoading] = useState(false);
  const [budgetResult, setBudgetResult] = useState<any>(null);

  // Blueprint Label State
  const [labels, setLabels] = useState<Label[]>([]);
  
  // Interaction State
  const containerRef = useRef<HTMLDivElement>(null);
  const [draggedLabelId, setDraggedLabelId] = useState<string | null>(null);
  const [resizingLabelId, setResizingLabelId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [initialResizeState, setInitialResizeState] = useState({ width: 0, height: 0, startX: 0, startY: 0 });

  const styleObj = ARCH_STYLES.find(s => s.id === selectedStyle);

  // Initialize Labels from Rooms
  useEffect(() => {
    if (rooms.length > 0) {
      const initialLabels: Label[] = rooms.map((room, index) => ({
        id: room.id,
        type: 'text',
        text: room.name,
        x: 40 + (index % 4) * 120, 
        y: 40 + Math.floor(index / 4) * 60
      }));
      setLabels(initialLabels);
    }
  }, [rooms]);

  // Handle Pro Toggle
  const handleTogglePro = async () => {
    if (!useProModel) {
      try {
        if (window.aistudio && !await window.aistudio.hasSelectedApiKey()) {
           await window.aistudio.openSelectKey();
        }
        setUseProModel(true);
        if (confirm("已切換至高畫質 Pro 模式。是否要重新生成 3D 模型？")) {
             setImage3D(null);
             setTimeout(handleGenerate3D, 100);
        }
      } catch (e) {
        setUseProModel(false);
      }
    } else {
      setUseProModel(false);
    }
  };

  const handleGenerate3D = async () => {
    if (image3D) return; 
    setLoading3D(true);
    try {
      const img = await generate3DPerspective(
          rooms, 
          styleObj?.promptModifier || '',
          floorPlanImage || undefined,
          useProModel
      );
      setImage3D(img);
    } catch (e) {
      console.error("Error generating 3D:", e instanceof Error ? e.message : String(e));
    } finally {
      setLoading3D(false);
    }
  };

  useEffect(() => {
    handleGenerate3D();
  }, []);

  const handleGeneratePanorama = async (roomName: string) => {
    setSelectedRoomForPanorama(roomName);
    setShowPanoramaModal(true);
    setLoadingPanorama(true);
    setPanoramaImage(null);
    try {
      const referenceImage = image3D || floorPlanImage || undefined;
      const img = await generatePanoramaView(
          roomName, 
          styleObj?.promptModifier || '',
          referenceImage,
          useProModel
      );
      setPanoramaImage(img);
    } catch (e) {
      console.error("Error generating panorama:", e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingPanorama(false);
    }
  };

  const handleEstimateBudget = async () => {
      setShowBudgetModal(true);
      if (budgetResult) return;
      
      setBudgetLoading(true);
      try {
          // Approximate area from room count or stored area (need to pass area prop if want precision, estimating for now)
          const estimatedArea = rooms.length * 15; // fallback
          const jsonStr = await generateBudgetEstimate(rooms, estimatedArea, styleObj?.name || '', image3D || undefined);
          setBudgetResult(JSON.parse(jsonStr));
      } catch (e) {
          console.error(e);
      } finally {
          setBudgetLoading(false);
      }
  };

  const handleDownloadPDF = () => {
    const element = document.getElementById('report-content');
    if (!element) return;
    // @ts-ignore
    if (typeof window.html2pdf === 'undefined') {
        alert('PDF 生成模組載入中，請稍候再試...');
        return;
    }
    const opt = {
      margin:       [0.2, 0.2, 0.2, 0.2],
      filename:     `AI_Architect_Design_${new Date().getTime()}.pdf`,
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { 
          scale: 2, 
          useCORS: true, 
          logging: false,
          scrollY: 0,
          windowWidth: 1280,
          ignoreElements: (element: Element) => element.classList.contains('no-print')
      },
      jsPDF:        { unit: 'in', format: 'a4', orientation: 'landscape' },
      pagebreak:    { mode: ['avoid-all', 'css', 'legacy'] }
    };
    // @ts-ignore
    window.html2pdf().set(opt).from(element).save();
  };

  // --- Interaction Logic (Drag & Resize) ---
  const handleMouseDown = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    e.preventDefault();
    const label = labels.find(l => l.id === id);
    if (!label || !containerRef.current) return;
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setDragOffset({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    setDraggedLabelId(id);
  };

  const handleResizeStart = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    e.preventDefault();
    const label = labels.find(l => l.id === id);
    if (!label) return;
    setResizingLabelId(id);
    setInitialResizeState({
      width: label.width || 100, height: label.height || 60,
      startX: e.clientX, startY: e.clientY
    });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    if (draggedLabelId) {
      const containerRect = containerRef.current.getBoundingClientRect();
      const newX = e.clientX - containerRect.left - dragOffset.x;
      const newY = e.clientY - containerRect.top - dragOffset.y;
      setLabels(prev => prev.map(l => l.id === draggedLabelId ? { ...l, x: newX, y: newY } : l));
    }
    if (resizingLabelId) {
      const deltaX = e.clientX - initialResizeState.startX;
      const deltaY = e.clientY - initialResizeState.startY;
      setLabels(prev => prev.map(l => l.id === resizingLabelId ? { 
          ...l, width: Math.max(20, initialResizeState.width + deltaX), height: Math.max(20, initialResizeState.height + deltaY)
      } : l));
    }
  };

  const handleMouseUp = () => {
    setDraggedLabelId(null);
    setResizingLabelId(null);
  };

  const handleLabelChange = (id: string, newText: string) => setLabels(prev => prev.map(l => l.id === id ? { ...l, text: newText } : l));
  const addNewLabel = () => setLabels(prev => [...prev, { id: Math.random().toString(36).substr(2, 9), type: 'text', text: '文字', x: 50, y: 50 }]);
  const addNewBlock = () => setLabels(prev => [...prev, { id: Math.random().toString(36).substr(2, 9), type: 'block', x: 150, y: 50, width: 100, height: 60 }]);
  const deleteLabel = (id: string) => setLabels(prev => prev.filter(l => l.id !== id));
  const clearAllLabels = () => setLabels([]);

  return (
    <div id="report-content" className="space-y-6 animate-fade-in pb-4 relative z-10 bg-white p-4 rounded-3xl">
      
      {/* Header Card */}
      <div className="bg-white p-6 rounded-3xl shadow-sm border border-gray-100 flex flex-col xl:flex-row justify-between items-center gap-4 relative z-30">
        <div>
           <h3 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
             設計完成 <span className="text-2xl animate-bounce">🎉</span>
           </h3>
           <p className="text-gray-500 text-sm mt-1">您的 {styleObj?.name.split(' ')[0]} 風格空間已生成完畢</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-3 no-print" data-html2canvas-ignore="true">
            <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg border border-gray-200 mr-2">
               <span className={`text-xs font-bold ${useProModel ? 'text-purple-600' : 'text-gray-500'}`}>✨ Pro Model</span>
               <button onClick={handleTogglePro} className={`w-8 h-4 rounded-full p-0.5 transition-colors duration-300 ${useProModel ? 'bg-purple-600' : 'bg-gray-300'}`}>
                  <div className={`w-3 h-3 bg-white rounded-full shadow-md transform transition-transform duration-300 ${useProModel ? 'translate-x-4' : 'translate-x-0'}`}></div>
               </button>
            </div>
            <Button variant="secondary" onClick={handleEstimateBudget} className="bg-green-50 text-green-700 border-green-200 hover:bg-green-100">
               💰 預算估價
            </Button>
            <Button variant="outline" onClick={onBack} className="border-gray-200 text-gray-600 hover:text-gray-900">← 返回</Button>
            <Button variant="outline" onClick={handleDownloadPDF} className="border-gray-200">📄 PDF</Button>
            <Button variant="primary" onClick={onRestart} className="bg-gray-900 text-white hover:bg-black shadow-lg">↺ 新專案</Button>
        </div>
      </div>

      {/* Main Content Tabs */}
      <div className="bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden min-h-[600px] flex flex-col relative z-20 print:border-0 print:shadow-none">
        <div className="flex border-b border-gray-100 no-print" data-html2canvas-ignore="true">
          <button onClick={() => setActiveTab('3d')} className={`flex-1 py-4 text-center font-bold text-sm tracking-wide transition-colors ${activeTab === '3d' ? 'bg-white text-brand-600 border-b-2 border-brand-600' : 'bg-gray-50 text-gray-400 hover:bg-gray-100'}`}>
            🧊 3D 透視模型 {useProModel && <span className="text-[10px] bg-purple-100 text-purple-700 px-1 rounded ml-1">PRO</span>}
          </button>
          <button onClick={() => setActiveTab('blueprint')} className={`flex-1 py-4 text-center font-bold text-sm tracking-wide transition-colors ${activeTab === 'blueprint' ? 'bg-white text-brand-600 border-b-2 border-brand-600' : 'bg-gray-50 text-gray-400 hover:bg-gray-100'}`}>
            📐 平面藍圖與標註
          </button>
        </div>

        <div className="flex-grow relative bg-gray-50 flex flex-col print:bg-white">
          {activeTab === '3d' && (
             <div className="w-full h-full flex flex-col">
                <div className="flex-grow relative flex items-center justify-center overflow-hidden bg-gray-100 min-h-[400px] print:bg-white group cursor-zoom-in" onClick={() => image3D && setShowLightbox(true)}>
                    {loading3D ? (
                        <div className="flex flex-col items-center text-gray-400">
                            <div className={`w-12 h-12 border-4 border-t-transparent rounded-full animate-spin mb-4 ${useProModel ? 'border-purple-500' : 'border-brand-500'}`}></div>
                            <span className="text-xs font-mono tracking-widest uppercase">Rendering 3D Model...</span>
                        </div>
                    ) : image3D ? (
                        <>
                            <img src={image3D} alt="3D Render" className="max-w-full max-h-full object-contain p-4 print:p-0 transition-transform group-hover:scale-105 duration-500" />
                            <div className="absolute top-4 right-4 bg-black/50 text-white p-2 rounded-full opacity-0 group-hover:opacity-100 transition-opacity no-print">🔍</div>
                            <div className="absolute bottom-4 right-4 no-print" data-html2canvas-ignore="true" onClick={(e) => e.stopPropagation()}>
                                <Button onClick={() => { setImage3D(null); handleGenerate3D(); }} variant="secondary" className="text-xs py-1 px-3 opacity-80 hover:opacity-100">
                                    ↻ 重新生成
                                </Button>
                            </div>
                        </>
                    ) : (
                        <div className="flex flex-col items-center gap-2">
                             <div className="text-red-400 text-sm bg-red-50 px-4 py-2 rounded-lg border border-red-100">生成失敗</div>
                             <Button onClick={handleGenerate3D} variant="outline" className="text-xs">重試</Button>
                        </div>
                    )}
                </div>
                <div className="p-6 bg-white border-t border-gray-100 no-print" data-html2canvas-ignore="true">
                    <h4 className="font-bold text-gray-800 mb-4 flex items-center gap-2 text-sm uppercase tracking-wider">
                        <span>👀 VR 全景預覽</span>
                    </h4>
                    <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-3">
                        {Array.from(new Set(rooms.map(r => r.name))).map(roomName => (
                            <button key={String(roomName)} onClick={() => handleGeneratePanorama(String(roomName))} className="group relative overflow-hidden rounded-xl bg-gray-800 aspect-square flex flex-col items-center justify-center hover:shadow-lg hover:-translate-y-1 transition-all duration-300">
                                <div className="absolute inset-0 bg-gradient-to-br from-gray-700 to-gray-900 group-hover:scale-110 transition-transform duration-700"></div>
                                <span className="relative z-10 text-xl mb-1 group-hover:scale-110 transition-transform">📷</span>
                                <span className="relative z-10 font-medium text-white text-xs">{roomName}</span>
                            </button>
                        ))}
                    </div>
                </div>
             </div>
          )}

          {activeTab === 'blueprint' && (
            <div className="w-full h-full flex flex-col animate-fade-in">
               <div className="p-3 bg-white border-b border-gray-100 flex flex-wrap justify-between items-center relative z-50 gap-2 no-print" data-html2canvas-ignore="true">
                  <div className="text-xs text-gray-500 px-2 flex items-center gap-2">
                     <span className="bg-brand-50 text-brand-700 px-2 py-0.5 rounded text-[10px] font-bold">TIPS</span>
                     <span>拖曳標籤或使用白色圖塊覆蓋原有文字。</span>
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={clearAllLabels} variant="outline" className="px-3 py-1 text-xs h-8 border-red-200 text-red-500 hover:bg-red-50">清除標籤</Button>
                    <Button onClick={addNewBlock} variant="secondary" className="px-3 py-1 text-xs h-8 bg-gray-100 text-gray-600">+ 空白圖塊</Button>
                    <Button onClick={addNewLabel} variant="secondary" className="px-3 py-1 text-xs h-8">+ 新增標籤</Button>
                  </div>
               </div>

               <div className="flex-grow relative overflow-hidden select-none bg-white cursor-crosshair flex items-center justify-center p-8 bg-grid-slate-50 print:p-0 print:block print:h-auto"
                 ref={containerRef} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}
                 style={{ backgroundImage: 'radial-gradient(#e2e8f0 1px, transparent 1px)', backgroundSize: '24px 24px' }}>
                 {floorPlanImage ? (
                    <img src={floorPlanImage} alt="Floor Plan" className="max-w-full max-h-full object-contain pointer-events-none shadow-xl border-4 border-white rounded-lg print:shadow-none print:border-0 print:max-h-none print:w-full" style={{ minHeight: '300px' }} />
                 ) : <span className="text-gray-300">無影像</span>}

                 {labels.map((label) => (
                   <div key={label.id}
                     className={`absolute group transition-shadow ${label.type === 'text' ? 'flex items-center gap-2 px-3 py-1.5' : ''} ${(draggedLabelId === label.id || resizingLabelId === label.id) ? 'z-50 ring-1 ring-brand-400' : 'z-20 hover:ring-1 hover:ring-gray-300 hover:ring-dashed print:ring-0'}`}
                     style={{ left: label.x, top: label.y, width: label.type === 'block' ? label.width : 'auto', height: label.type === 'block' ? label.height : 'auto', cursor: 'move', backgroundColor: '#ffffff', touchAction: 'none' }}
                     onMouseDown={(e) => handleMouseDown(e, label.id)}
                   >
                     {label.type === 'text' && (
                        <>
                          <input type="text" value={label.text} onChange={(e) => handleLabelChange(label.id, e.target.value)} className="bg-transparent border-none outline-none text-sm font-bold text-gray-800 w-24 text-center cursor-text pointer-events-auto placeholder-gray-300 print:w-auto" placeholder="輸入文字" onMouseDown={(e) => e.stopPropagation()} />
                          <button onClick={(e) => { e.stopPropagation(); deleteLabel(label.id); }} className="text-gray-300 hover:text-red-500 text-xs opacity-0 group-hover:opacity-100 transition-opacity w-4 h-4 flex items-center justify-center rounded-full hover:bg-red-50 absolute -top-2 -right-2 bg-white border border-gray-100 shadow-sm no-print" data-html2canvas-ignore="true">×</button>
                        </>
                     )}
                     {label.type === 'block' && (
                       <>
                          <div className="w-full h-full opacity-0 group-hover:opacity-10 pointer-events-none bg-blue-500 print:opacity-0"></div>
                          <button onClick={(e) => { e.stopPropagation(); deleteLabel(label.id); }} className="text-gray-300 hover:text-red-500 text-xs opacity-0 group-hover:opacity-100 transition-opacity w-5 h-5 flex items-center justify-center rounded-full bg-white hover:bg-red-50 absolute -top-2 -right-2 shadow-sm border border-gray-100 z-50 no-print" data-html2canvas-ignore="true">×</button>
                          <div className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize opacity-0 group-hover:opacity-50 hover:!opacity-100 bg-brand-500 rounded-tl-lg z-50 no-print" onMouseDown={(e) => handleResizeStart(e, label.id)} data-html2canvas-ignore="true"></div>
                       </>
                     )}
                   </div>
                 ))}
               </div>
            </div>
          )}
        </div>
      </div>

      {/* Lightbox Modal */}
      {showLightbox && image3D && (
          <div className="fixed inset-0 z-[120] bg-black/95 flex items-center justify-center p-4 cursor-zoom-out animate-fade-in no-print" onClick={() => setShowLightbox(false)} data-html2canvas-ignore="true">
              <img src={image3D} alt="Full Screen" className="max-w-full max-h-full object-contain" />
              <button onClick={() => setShowLightbox(false)} className="absolute top-6 right-6 text-white text-xl bg-white/10 rounded-full p-3 hover:bg-white/20">✕</button>
          </div>
      )}

      {/* Panorama Modal */}
      {showPanoramaModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/90 backdrop-blur-md animate-fade-in no-print" data-html2canvas-ignore="true">
          <button onClick={() => setShowPanoramaModal(false)} className="absolute top-6 right-6 text-white/50 hover:text-white z-50 transition-colors bg-white/10 rounded-full p-2"><svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg></button>
          <div className="w-full max-w-6xl aspect-[2/1] bg-gray-800 rounded-2xl overflow-hidden relative flex items-center justify-center shadow-2xl border border-gray-700 ring-1 ring-white/10">
            {loadingPanorama ? (
                 <div className="text-center text-white">
                    <div className={`w-16 h-16 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-6 ${useProModel ? 'border-purple-500' : 'border-brand-500'}`}></div>
                    <p className="text-xl font-light tracking-wide">GENERATING 360° VIEW</p>
                 </div>
            ) : panoramaImage ? (
                <div className="w-full h-full relative">
                    <PanoramaViewer imageUrl={panoramaImage} />
                    <div className="absolute top-6 left-6 bg-black/60 backdrop-blur text-white px-4 py-2 rounded-full border border-white/10 pointer-events-none select-none">
                       <span className="font-bold">{selectedRoomForPanorama}</span> • 360° VR
                    </div>
                </div>
            ) : <div className="text-red-400">無法生成全景圖</div>}
          </div>
        </div>
      )}

      {/* Budget Modal */}
      {showBudgetModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in no-print" data-html2canvas-ignore="true">
              <div className="bg-white w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
                  <div className="p-5 border-b border-gray-100 flex justify-between items-center bg-green-50">
                      <h3 className="font-bold text-green-800 flex items-center gap-2">💰 AI 裝修預算估算</h3>
                      <button onClick={() => setShowBudgetModal(false)} className="text-gray-400 hover:text-gray-600">✕</button>
                  </div>
                  <div className="p-6 overflow-y-auto">
                      {budgetLoading ? (
                          <div className="flex flex-col items-center py-8">
                              <div className="w-10 h-10 border-4 border-green-200 border-t-green-600 rounded-full animate-spin mb-4"></div>
                              <p className="text-gray-500">正在分析建材與計算成本...</p>
                          </div>
                      ) : budgetResult ? (
                          <div className="space-y-4">
                              <div className="bg-gray-50 p-4 rounded-xl text-center">
                                  <p className="text-xs text-gray-500 uppercase tracking-wide">預估總價範圍</p>
                                  <p className="text-2xl font-bold text-gray-800">{budgetResult.total_range}</p>
                                  <div className="inline-block mt-2 px-2 py-1 bg-white border border-gray-200 rounded text-xs text-gray-500">{budgetResult.level}</div>
                              </div>
                              <div className="space-y-2">
                                  <h4 className="font-bold text-sm text-gray-700">細項預估</h4>
                                  {budgetResult.breakdown?.map((item: any, i: number) => (
                                      <div key={i} className="flex justify-between text-sm border-b border-gray-50 pb-2 last:border-0">
                                          <span className="text-gray-600">{item.item}</span>
                                          <span className="font-medium text-gray-800">{item.cost}</span>
                                      </div>
                                  ))}
                              </div>
                              <div className="bg-yellow-50 p-4 rounded-xl text-sm text-yellow-800 border border-yellow-100">
                                  <span className="font-bold mr-1">💡 專家建議:</span>
                                  {budgetResult.advice}
                              </div>
                              <p className="text-[10px] text-gray-400 text-center mt-4">*此估價僅供參考，實際費用請諮詢專業裝修公司。</p>
                          </div>
                      ) : <p className="text-center text-red-400">估算失敗，請重試。</p>}
                  </div>
              </div>
          </div>
      )}
    </div>
  );
};
