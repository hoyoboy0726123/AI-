

import React, { useRef, useState, useEffect } from 'react';
import { Button } from './Button';
import { ROOM_TYPES, PlacedRoom, StructuralItem, StructureType } from '../types';
import { generateDesignCritique } from '../services/geminiService';

interface Props {
  rooms: PlacedRoom[];
  setRooms: React.Dispatch<React.SetStateAction<PlacedRoom[]>>;
  structures: StructuralItem[];
  setStructures: React.Dispatch<React.SetStateAction<StructuralItem[]>>;
  area: number;
  shape: 'square' | 'rectangle';
  onNext: () => void;
  onPrev: () => void;
}

export const Step2RoomLayout: React.FC<Props> = ({ rooms, setRooms, structures, setStructures, area, shape, onNext, onPrev }) => {
  
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [selectedStructureId, setSelectedStructureId] = useState<string | null>(null);
  
  // Interaction State
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dragType, setDragType] = useState<'room' | 'structure' | null>(null);

  const [resizingId, setResizingId] = useState<string | null>(null);
  const [resizeType, setResizeType] = useState<'room' | 'structure' | null>(null);
  
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 }); // % offset
  const [initialResize, setInitialResize] = useState({ w: 0, h: 0, x: 0, y: 0 }); // pixels

  // AI Critique State
  const [critiqueLoading, setCritiqueLoading] = useState(false);
  const [critiqueResult, setCritiqueResult] = useState<string | null>(null);
  const [showCritiqueModal, setShowCritiqueModal] = useState(false);

  // Helper: Calculate Real Dimensions
  const getDimensions = (pctW: number, pctH: number) => {
     let totalW, totalH;
     if (shape === 'square') {
         totalW = Math.sqrt(area);
         totalH = totalW;
     } else {
         totalH = Math.sqrt(area * 0.75);
         totalW = totalH * (4/3);
     }
     
     const wM = (pctW / 100) * totalW;
     const hM = (pctH / 100) * totalH;
     const areaM = wM * hM;
     const ping = areaM * 0.3025;
     
     return {
         w: wM.toFixed(1),
         h: hM.toFixed(1),
         m2: areaM.toFixed(1),
         ping: ping.toFixed(1)
     };
  };

  // Helper: Collision Detection (Only for rooms)
  const checkCollision = (id: string, currentRooms: PlacedRoom[]) => {
      const target = currentRooms.find(r => r.id === id);
      if (!target) return false;
      
      return currentRooms.some(other => {
          if (other.id === id) return false;
          return !(
              target.x + target.width <= other.x ||
              target.x >= other.x + other.width ||
              target.y + target.height <= other.y ||
              target.y >= other.y + other.height
          );
      });
  };

  // Deselect when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
        if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
            setSelectedRoomId(null);
            setSelectedStructureId(null);
        }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const addRoom = (typeId: string) => {
    const type = ROOM_TYPES.find(r => r.id === typeId);
    if (!type) return;
    
    const offset = rooms.length * 5;
    const newRoom: PlacedRoom = {
      id: Math.random().toString(36).substr(2, 9),
      typeId: type.id,
      name: type.name,
      color: type.color,
      width: 25, 
      height: 20, 
      x: 10 + (offset % 50),
      y: 10 + (offset % 50),
    };
    setRooms([...rooms, newRoom]);
    setSelectedRoomId(newRoom.id);
    setSelectedStructureId(null);
  };

  const addStructure = (type: StructureType) => {
      let width = 20;
      let height = 2;

      if (type === 'door') { width = 8; height = 8; }
      else if (type === 'window') { width = 12; height = 2; }
      else if (type === 'wall') { width = 20; height = 2; }
      else if (type === 'cabinet') { width = 15; height = 5; }
      else if (type === 'custom') { width = 15; height = 15; }

      const newStruct: StructuralItem = {
          id: Math.random().toString(36).substr(2, 9),
          type: type,
          x: 45,
          y: 45,
          width: width,
          height: height,
          rotation: 0
      };
      setStructures([...structures, newStruct]);
      setSelectedStructureId(newStruct.id);
      setSelectedRoomId(null);
  };

  const removeRoom = (id: string) => {
    setRooms(rooms.filter(r => r.id !== id));
    if (selectedRoomId === id) setSelectedRoomId(null);
  };

  const removeStructure = (id: string) => {
      setStructures(structures.filter(s => s.id !== id));
      if (selectedStructureId === id) setSelectedStructureId(null);
  };

  const rotateStructure = (id: string) => {
      setStructures(structures.map(s => {
          if (s.id === id) {
              const newRot = (s.rotation + 90) % 360;
              return { ...s, rotation: newRot };
          }
          return s;
      }));
  };

  // Keyboard shortcut for rotation
  useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
          if ((e.key === 'r' || e.key === 'R') && selectedStructureId) {
              rotateStructure(selectedStructureId);
          }
          if ((e.key === 'Delete' || e.key === 'Backspace')) {
             if (selectedRoomId) removeRoom(selectedRoomId);
             if (selectedStructureId) removeStructure(selectedStructureId);
          }
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedStructureId, selectedRoomId, structures, rooms]);

  const handleMouseDown = (e: React.MouseEvent, id: string, type: 'room' | 'structure') => {
    if (resizingId) return;
    e.stopPropagation();
    e.preventDefault();
    
    if (type === 'room') {
        const room = rooms.find(r => r.id === id);
        if (!room || !containerRef.current) return;
        setSelectedRoomId(id);
        setSelectedStructureId(null);
        setDraggedId(id);
        setDragType('room');
        const containerRect = containerRef.current.getBoundingClientRect();
        const mouseXPct = ((e.clientX - containerRect.left) / containerRect.width) * 100;
        const mouseYPct = ((e.clientY - containerRect.top) / containerRect.height) * 100;
        setDragOffset({ x: mouseXPct - room.x, y: mouseYPct - room.y });
    } else {
        const struct = structures.find(s => s.id === id);
        if (!struct || !containerRef.current) return;
        setSelectedStructureId(id);
        setSelectedRoomId(null);
        setDraggedId(id);
        setDragType('structure');
        const containerRect = containerRef.current.getBoundingClientRect();
        const mouseXPct = ((e.clientX - containerRect.left) / containerRect.width) * 100;
        const mouseYPct = ((e.clientY - containerRect.top) / containerRect.height) * 100;
        setDragOffset({ x: mouseXPct - struct.x, y: mouseYPct - struct.y });
    }
  };

  const handleResizeStart = (e: React.MouseEvent, id: string, type: 'room' | 'structure') => {
    e.stopPropagation();
    e.preventDefault();
    setResizingId(id);
    setResizeType(type);
    if (type === 'room') setSelectedRoomId(id);
    else setSelectedStructureId(id);
    
    const item = type === 'room' ? rooms.find(r => r.id === id) : structures.find(s => s.id === id);
    if (item) {
        setInitialResize({
            w: item.width,
            h: item.height,
            x: e.clientX,
            y: e.clientY
        });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();

    if (draggedId) {
        const mouseXPct = ((e.clientX - containerRect.left) / containerRect.width) * 100;
        const mouseYPct = ((e.clientY - containerRect.top) / containerRect.height) * 100;

        let newX = mouseXPct - dragOffset.x;
        let newY = mouseYPct - dragOffset.y;
        
        // Snap to grid (1.25% for finer control)
        newX = Math.round(newX / 1.25) * 1.25;
        newY = Math.round(newY / 1.25) * 1.25;

        if (dragType === 'room') {
            const room = rooms.find(r => r.id === draggedId);
            if (room) {
                newX = Math.max(0, Math.min(100 - room.width, newX));
                newY = Math.max(0, Math.min(100 - room.height, newY));
                setRooms(prev => prev.map(r => r.id === draggedId ? { ...r, x: newX, y: newY } : r));
            }
        } else {
            const s = structures.find(i => i.id === draggedId);
            if (s) {
                 newX = Math.max(0, Math.min(100, newX));
                 newY = Math.max(0, Math.min(100, newY));
                 setStructures(prev => prev.map(i => i.id === draggedId ? { ...i, x: newX, y: newY } : i));
            }
        }
    }

    if (resizingId) {
        const deltaX = e.clientX - initialResize.x;
        const deltaY = e.clientY - initialResize.y;
        const deltaXPct = (deltaX / containerRect.width) * 100;
        const deltaYPct = (deltaY / containerRect.height) * 100;

        if (resizeType === 'room') {
            setRooms(prev => prev.map(r => {
                if (r.id === resizingId) {
                    let newW = initialResize.w + deltaXPct;
                    let newH = initialResize.h + deltaYPct;
                    newW = Math.round(newW / 1.25) * 1.25;
                    newH = Math.round(newH / 1.25) * 1.25;
                    newW = Math.max(5, Math.min(100 - r.x, newW));
                    newH = Math.max(5, Math.min(100 - r.y, newH));
                    return { ...r, width: newW, height: newH };
                }
                return r;
            }));
        } else {
             // Structure resizing
             setStructures(prev => prev.map(s => {
                 if (s.id === resizingId) {
                     let newW = initialResize.w + deltaXPct;
                     let newH = s.height;
                     
                     newW = Math.round(newW / 1.25) * 1.25;
                     newW = Math.max(2, newW); // Minimum size constraint

                     // Allow 2D resizing for cabinet and custom
                     if (s.type === 'cabinet' || s.type === 'custom') {
                         newH = initialResize.h + deltaYPct;
                         newH = Math.round(newH / 1.25) * 1.25;
                         newH = Math.max(2, newH);
                     }

                     return { ...s, width: newW, height: newH };
                 }
                 return s;
             }));
        }
    }
  };

  const handleMouseUp = () => {
    setDraggedId(null);
    setResizingId(null);
    setDragType(null);
    setResizeType(null);
  };

  const handleAnalyze = async () => {
      setCritiqueLoading(true);
      setShowCritiqueModal(true);
      try {
          const result = await generateDesignCritique(rooms, area, shape);
          setCritiqueResult(result);
      } catch (e) {
          setCritiqueResult("分析失敗，請稍後再試。");
      } finally {
          setCritiqueLoading(false);
      }
  };

  const containerAspect = shape === 'square' ? 'aspect-square' : 'aspect-[4/3]';

  return (
    <div className="space-y-6 animate-fade-in h-full flex flex-col relative">
      <div className="bg-white/90 backdrop-blur-sm p-6 rounded-3xl shadow-sm border border-gray-100 flex-grow flex flex-col">
        <div className="flex justify-between items-center mb-6">
            <div>
                <h3 className="text-xl font-bold text-gray-800">2. 空間規劃拼圖</h3>
                <p className="text-gray-500 text-sm">磁吸對齊網格，重疊時會顯示警示。</p>
            </div>
            <div className="flex gap-3">
                <Button 
                    onClick={handleAnalyze} 
                    variant="secondary" 
                    className="bg-indigo-50 text-indigo-600 border border-indigo-100 hover:bg-indigo-100"
                    disabled={rooms.length === 0}
                >
                    ✨ AI 佈局分析
                </Button>
                <div className="bg-brand-50 px-4 py-2 rounded-lg text-brand-700 font-mono text-sm flex items-center">
                    已配置: {rooms.length + structures.length}
                </div>
            </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 flex-grow">
          {/* Palette */}
          <div className="order-2 lg:order-1 flex flex-col gap-6">
            
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">房間 (Rooms)</h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-3">
                {ROOM_TYPES.map(type => (
                  <button
                    key={type.id}
                    onClick={() => addRoom(type.id)}
                    className="group flex flex-row lg:flex-col items-center lg:justify-center p-3 rounded-xl border border-gray-100 hover:border-brand-300 hover:bg-brand-50 transition-all active:scale-95 bg-white shadow-sm"
                  >
                    <span className="text-xl mr-2 lg:mr-0 lg:mb-1">{type.icon}</span>
                    <span className="text-xs font-medium text-gray-600 group-hover:text-brand-700">{type.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-3 pt-4 border-t border-gray-100">
               <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider">結構元件 (Structures)</h4>
               <div className="grid grid-cols-3 gap-2">
                   <button onClick={() => addStructure('wall')} className="flex flex-col items-center p-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg active:scale-95">
                       <div className="w-8 h-1 bg-gray-800 mb-1"></div>
                       <span className="text-xs text-gray-600">牆壁</span>
                   </button>
                   <button onClick={() => addStructure('window')} className="flex flex-col items-center p-2 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg active:scale-95">
                       <div className="w-8 h-2 border border-blue-400 bg-blue-200 mb-1"></div>
                       <span className="text-xs text-gray-600">窗戶</span>
                   </button>
                   <button onClick={() => addStructure('door')} className="flex flex-col items-center p-2 bg-yellow-50 hover:bg-yellow-100 border border-yellow-200 rounded-lg active:scale-95">
                       <svg width="24" height="24" viewBox="0 0 24 24" className="mb-1">
                           <path d="M4 20h2v-8h8v8h2" stroke="currentColor" fill="none" strokeWidth="2" className="text-yellow-800"/>
                           <path d="M6 12a8 8 0 0 1 8 8" stroke="currentColor" fill="none" strokeWidth="1" className="text-yellow-600"/>
                       </svg>
                       <span className="text-xs text-gray-600">門</span>
                   </button>
                   <button onClick={() => addStructure('cabinet')} className="flex flex-col items-center p-2 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg active:scale-95">
                       <div className="w-8 h-4 border border-amber-400 bg-amber-100 mb-1 flex items-center justify-center relative overflow-hidden">
                           <div className="absolute inset-0 border-t border-amber-400 transform rotate-12 scale-150"></div>
                           <div className="absolute inset-0 border-t border-amber-400 transform -rotate-12 scale-150"></div>
                       </div>
                       <span className="text-xs text-gray-600">櫃子</span>
                   </button>
                   <button onClick={() => addStructure('custom')} className="flex flex-col items-center p-2 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-lg active:scale-95">
                       <div className="w-8 h-4 border border-dashed border-purple-400 bg-purple-100 mb-1"></div>
                       <span className="text-xs text-gray-600">自定義</span>
                   </button>
               </div>
            </div>

          </div>

          {/* Canvas */}
          <div className="order-1 lg:order-2 lg:col-span-2 bg-[#2d3748] rounded-2xl border-4 border-gray-800 p-8 flex items-center justify-center relative overflow-hidden shadow-inner select-none">
            {/* Grid 2.5% */}
            <div className="absolute inset-0 opacity-10 pointer-events-none" 
                 style={{ 
                    backgroundImage: 'linear-gradient(#ffffff 1px, transparent 1px), linear-gradient(90deg, #ffffff 1px, transparent 1px)', 
                    backgroundSize: '2.5% 2.5%' 
                 }}>
            </div>
            
            <div 
                className={`w-full max-w-md ${containerAspect} bg-white/5 border-2 border-white/30 rounded-lg relative shadow-2xl transition-all overflow-hidden cursor-crosshair`}
                ref={containerRef}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
            >
               {/* Rooms */}
               {rooms.map((room) => {
                 const isCollision = checkCollision(room.id, rooms);
                 const dims = getDimensions(room.width, room.height);
                 
                 return (
                 <div 
                  key={room.id}
                  onMouseDown={(e) => handleMouseDown(e, room.id, 'room')}
                  className={`absolute flex flex-col items-center justify-center transition-all select-none
                    ${room.color.replace('bg-', 'bg-opacity-90 bg-')} 
                    ${selectedRoomId === room.id ? 'z-30 ring-2 ring-white shadow-xl' : 'z-10 hover:z-20 hover:ring-1 hover:ring-white/50'}
                    ${isCollision ? 'ring-2 ring-red-500 !bg-red-100/90' : ''}
                  `}
                  style={{ 
                    left: `${room.x}%`, top: `${room.y}%`, width: `${room.width}%`, height: `${room.height}%`,
                    cursor: 'grab', borderRadius: '4px'
                  }}
                 >
                    <span className="text-xl drop-shadow-sm pointer-events-none">{ROOM_TYPES.find(t => t.id === room.typeId)?.icon}</span>
                    <span className="text-[10px] font-bold mt-1 text-gray-800 pointer-events-none whitespace-nowrap overflow-hidden text-ellipsis max-w-full px-1">{room.name}</span>
                    {/* Measurements */}
                    {selectedRoomId === room.id && (
                        <div className="absolute -bottom-8 bg-black/80 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap z-50 pointer-events-none backdrop-blur-sm">
                            {dims.w}m x {dims.h}m ({dims.ping}坪)
                        </div>
                    )}
                    {/* Delete */}
                    {(selectedRoomId === room.id) && (
                        <button 
                            onClick={(e) => { e.stopPropagation(); removeRoom(room.id); }}
                            className="absolute -top-2 -right-2 bg-red-500 text-white w-5 h-5 rounded-full flex items-center justify-center shadow-md text-xs hover:bg-red-600 z-50 cursor-pointer"
                        >×</button>
                    )}
                    {/* Resize */}
                    <div 
                        onMouseDown={(e) => handleResizeStart(e, room.id, 'room')}
                        className="absolute bottom-0 right-0 w-6 h-6 cursor-se-resize flex items-end justify-end p-1 opacity-0 hover:opacity-100 transition-opacity"
                    >
                        <div className="w-2 h-2 bg-gray-600/50 rounded-sm"></div>
                    </div>
                 </div>
               )})}

               {/* Structures */}
               {structures.map((s) => (
                   <div
                     key={s.id}
                     onMouseDown={(e) => handleMouseDown(e, s.id, 'structure')}
                     className={`absolute transition-all select-none flex items-center justify-center ${selectedStructureId === s.id ? 'z-50 ring-1 ring-yellow-400' : 'z-40'}`}
                     style={{
                         left: `${s.x}%`, top: `${s.y}%`, width: `${s.width}%`, height: `${s.height}%`,
                         transform: `rotate(${s.rotation}deg)`,
                         cursor: 'grab'
                     }}
                   >
                       {s.type === 'wall' && <div className="w-full h-full bg-gray-800 border border-gray-600 shadow-sm"></div>}
                       
                       {s.type === 'window' && (
                           <div className="w-full h-full bg-blue-300/60 border border-blue-400 shadow-sm relative">
                               <div className="absolute inset-x-0 top-1/2 h-px bg-blue-500/50"></div>
                           </div>
                       )}

                       {s.type === 'door' && (
                           <div className="w-full h-full relative">
                               {/* Simple door representation: A line for the door leaf, and arc for swing */}
                               <div className="absolute left-0 bottom-0 w-1 h-full bg-amber-800"></div> {/* Hinge/Frame */}
                               <div className="absolute left-0 bottom-0 h-1 bg-amber-600 origin-left transform -rotate-45" style={{ width: '100%' }}></div> {/* Leaf */}
                               <div className="absolute left-0 bottom-0 w-full h-full rounded-tr-full border-t border-r border-amber-800/30"></div> {/* Swing arc */}
                           </div>
                       )}

                       {s.type === 'cabinet' && (
                           <div className="w-full h-full bg-amber-100 border border-amber-400 relative shadow-sm overflow-hidden">
                               {/* X mark for cabinet/storage */}
                               <svg className="absolute inset-0 w-full h-full text-amber-400/50" preserveAspectRatio="none">
                                   <line x1="0" y1="0" x2="100%" y2="100%" stroke="currentColor" strokeWidth="1" />
                                   <line x1="100%" y1="0" x2="0" y2="100%" stroke="currentColor" strokeWidth="1" />
                               </svg>
                           </div>
                       )}

                       {s.type === 'custom' && (
                           <div className="w-full h-full bg-purple-100/40 border-2 border-dashed border-purple-400 relative">
                               <div className="absolute inset-0 flex items-center justify-center text-[8px] text-purple-700 font-bold opacity-50 tracking-widest">CUSTOM</div>
                           </div>
                       )}

                       {selectedStructureId === s.id && (
                          <>
                             <button onClick={(e) => { e.stopPropagation(); removeStructure(s.id); }} className="absolute -top-4 -right-4 w-4 h-4 bg-red-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-red-600 transform -rotate-0 z-50">×</button>
                             <button onClick={(e) => { e.stopPropagation(); rotateStructure(s.id); }} className="absolute -top-4 -left-4 w-4 h-4 bg-blue-500 text-white rounded-full flex items-center justify-center text-xs hover:bg-blue-600 transform -rotate-0 z-50">↻</button>
                             {s.type !== 'door' && (
                                <div onMouseDown={(e) => handleResizeStart(e, s.id, 'structure')} className="absolute right-0 bottom-0 w-4 h-4 cursor-se-resize flex items-end justify-end p-1">
                                    <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
                                </div>
                             )}
                          </>
                       )}
                   </div>
               ))}

            </div>
            <div className="absolute bottom-4 right-4 text-white/40 font-mono text-xs pointer-events-none">
               Grid: 1.25% Step
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center bg-white/50 backdrop-blur px-6 py-4 rounded-2xl border border-gray-100">
        <Button onClick={onPrev} variant="outline" className="border-gray-300 text-gray-500">← 返回設定</Button>
        <div className="flex gap-3">
           <Button onClick={() => { setRooms([]); setStructures([]); }} variant="danger" disabled={rooms.length === 0 && structures.length === 0} className="bg-red-50 text-red-400 hover:bg-red-100 border border-transparent">清空</Button>
           <Button onClick={onNext} disabled={rooms.length === 0} className="bg-brand-600 hover:bg-brand-700 text-white shadow-lg shadow-brand-200">確認佈局，生成藍圖 →</Button>
        </div>
      </div>

      {/* Critique Modal */}
      {showCritiqueModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
              <div className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[80vh]">
                  <div className="p-6 border-b border-gray-100 flex justify-between items-center bg-indigo-50">
                      <h3 className="font-bold text-indigo-900 flex items-center gap-2">
                          <span className="text-xl">🔮</span> AI 設計風水顧問
                      </h3>
                      <button onClick={() => setShowCritiqueModal(false)} className="text-gray-400 hover:text-gray-600 text-2xl">×</button>
                  </div>
                  <div className="p-6 overflow-y-auto">
                      {critiqueLoading ? (
                          <div className="space-y-4 animate-pulse">
                              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                              <div className="h-32 bg-gray-100 rounded-xl mt-4"></div>
                              <p className="text-center text-gray-400 text-sm mt-4">AI 正在分析您的格局與風水...</p>
                          </div>
                      ) : (
                          <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap leading-relaxed">
                              {critiqueResult}
                          </div>
                      )}
                  </div>
                  <div className="p-4 border-t border-gray-100 flex justify-end">
                      <Button onClick={() => setShowCritiqueModal(false)}>關閉</Button>
                  </div>
              </div>
          </div>
      )}
    </div>
  );
};