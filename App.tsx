
import React, { useState, useEffect, useRef } from 'react';
import { StepIndicator } from './components/StepIndicator';
import { Step1PlotSize } from './components/Step1PlotSize';
import { Step2RoomLayout } from './components/Step2RoomLayout';
import { Step3StyleSelection } from './components/Step3StyleSelection';
import { Step4FinalResult } from './components/Step4FinalResult';
import { PlacedRoom, ARCH_STYLES, ProjectData, StructuralItem } from './types';
import { saveProject, loadProject } from './utils/db';

function App() {
  const [currentStep, setCurrentStep] = useState(1);
  const [area, setArea] = useState(100);
  const [shape, setShape] = useState<'square' | 'rectangle'>('square');
  const [rooms, setRooms] = useState<PlacedRoom[]>([]);
  const [structures, setStructures] = useState<StructuralItem[]>([]);
  const [selectedStyle, setSelectedStyle] = useState(ARCH_STYLES[0].id);
  const [generatedPlanImage, setGeneratedPlanImage] = useState<string | null>(null);
  const [useProModel, setUseProModel] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load from IndexedDB on mount
  useEffect(() => {
      const initLoad = async () => {
          try {
              const data = await loadProject('current_project');
              if (data) {
                  setArea(data.area);
                  setShape(data.shape);
                  setRooms(data.rooms);
                  setStructures(data.structures || []);
                  setSelectedStyle(data.selectedStyle);
                  setGeneratedPlanImage(data.generatedPlanImage);
                  setUseProModel(data.useProModel);
                  // Optionally restore step, or stay at 1 if completed
                  if (data.currentStep) setCurrentStep(data.currentStep);
              }
          } catch (e) {
              console.error("Failed to load project", e);
          }
      };
      initLoad();
  }, []);

  const handleCloudSave = async () => {
    setSaveStatus('saving');
    const projectData: ProjectData = {
      version: 1,
      timestamp: new Date().toISOString(),
      currentStep, area, shape, rooms, structures, selectedStyle, generatedPlanImage, useProModel
    };
    try {
      await saveProject('current_project', projectData);
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (e) {
      console.error("Save failed", e);
      setSaveStatus('error');
      setTimeout(() => setSaveStatus('idle'), 3000);
    }
  };

  const handleExport = async () => {
      const projectData: ProjectData = {
          version: 1,
          timestamp: new Date().toISOString(),
          currentStep, area, shape, rooms, structures, selectedStyle, generatedPlanImage, useProModel
      };
      const blob = new Blob([JSON.stringify(projectData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `AI_Architect_Project_${new Date().toISOString().slice(0,10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
  };

  const handleImportClick = () => fileInputRef.current?.click();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
          try {
              const data = JSON.parse(ev.target?.result as string) as ProjectData;
              if (data.version === 1) {
                  setArea(data.area);
                  setShape(data.shape);
                  setRooms(data.rooms);
                  setStructures(data.structures || []);
                  setSelectedStyle(data.selectedStyle);
                  setGeneratedPlanImage(data.generatedPlanImage);
                  setUseProModel(data.useProModel);
                  setCurrentStep(data.currentStep || 1);
                  alert("專案匯入成功！");
              } else {
                  alert("不支援的檔案版本");
              }
          } catch (err) {
              alert("檔案格式錯誤");
          }
      };
      reader.readAsText(file);
      // Reset input
      e.target.value = '';
  };

  const nextStep = () => setCurrentStep(prev => Math.min(prev + 1, 4));
  const prevStep = () => setCurrentStep(prev => Math.max(prev - 1, 1));
  const jumpToStep = (stepId: number) => {
      if (stepId < currentStep) setCurrentStep(stepId);
      else if (stepId === currentStep) {}
      else {
          if (stepId === 2 && currentStep === 1) nextStep();
          if (stepId === 3 && rooms.length > 0) setCurrentStep(3);
          if (stepId === 4 && generatedPlanImage) setCurrentStep(4);
      }
  };

  const restart = () => {
    setRooms([]);
    setStructures([]);
    setGeneratedPlanImage(null);
    setCurrentStep(1);
    setUseProModel(false);
  };

  return (
    <div className="min-h-screen flex flex-col items-center py-6 px-4 sm:px-6 relative">
      <header className="w-full max-w-6xl flex justify-between items-center mb-6 bg-white/80 backdrop-blur p-4 rounded-full shadow-sm border border-white/50 sticky top-4 z-[40] no-print">
        <div className="flex items-center gap-3 pl-2">
          <div className="bg-brand-600 text-white p-2 rounded-xl shadow-lg shadow-brand-500/30">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <div className="leading-tight">
            <h1 className="text-lg font-bold text-gray-900 tracking-tight">AI 建築師</h1>
            <p className="text-[10px] text-gray-500 font-medium tracking-wide uppercase">Generative Design</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2 pr-1">
           {/* Export/Import Buttons */}
           <div className="hidden md:flex gap-1 mr-2">
               <button onClick={handleExport} className="px-3 py-1.5 text-xs bg-white border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 flex items-center gap-1">
                 📤 匯出
               </button>
               <button onClick={handleImportClick} className="px-3 py-1.5 text-xs bg-white border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 flex items-center gap-1">
                 📥 匯入
               </button>
               <input type="file" ref={fileInputRef} onChange={handleFileChange} accept=".json" className="hidden" />
           </div>

           <button 
             onClick={handleCloudSave}
             disabled={saveStatus !== 'idle'}
             className={`hidden sm:flex items-center gap-1.5 px-4 py-2 text-sm rounded-full transition-all duration-300
               ${saveStatus === 'saved' ? 'bg-green-50 text-green-600 border border-green-200' : 
                 saveStatus === 'error' ? 'bg-red-50 text-red-600 border border-red-200' :
                 'text-gray-600 hover:text-brand-600 hover:bg-brand-50'}
             `}
           >
              {saveStatus === 'saving' ? (
                <><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg><span>儲存中...</span></>
              ) : saveStatus === 'saved' ? (
                <><span className="text-lg">✓</span><span>已儲存</span></>
              ) : saveStatus === 'error' ? (
                <span>⚠️ 失敗</span>
              ) : (
                <><span>☁️</span><span>雲端存檔</span></>
              )}
           </button>
           <div className="w-8 h-8 rounded-full bg-gray-200 border-2 border-white shadow-sm overflow-hidden">
              <img src="https://api.dicebear.com/7.x/avataaars/svg?seed=Architect" alt="User" />
           </div>
        </div>
      </header>

      <main className="w-full max-w-6xl flex flex-col flex-grow relative z-[10] mt-4">
        <div className="mb-8 no-print"><StepIndicator currentStep={currentStep} onStepClick={jumpToStep} /></div>
        
        <div className="flex-grow transition-all duration-300 relative">
          {currentStep === 1 && <Step1PlotSize area={area} setArea={setArea} shape={shape} setShape={setShape} onNext={nextStep} />}
          {currentStep === 2 && <Step2RoomLayout rooms={rooms} setRooms={setRooms} structures={structures} setStructures={setStructures} area={area} shape={shape} onNext={nextStep} onPrev={prevStep} />}
          {currentStep === 3 && <Step3StyleSelection selectedStyle={selectedStyle} setSelectedStyle={setSelectedStyle} generatedImage={generatedPlanImage} setGeneratedImage={setGeneratedPlanImage} area={area} shape={shape} rooms={rooms} structures={structures} onNext={nextStep} onPrev={prevStep} useProModel={useProModel} setUseProModel={setUseProModel} />}
          {currentStep === 4 && <Step4FinalResult rooms={rooms} structures={structures} selectedStyle={selectedStyle} floorPlanImage={generatedPlanImage} onRestart={restart} onBack={prevStep} useProModel={useProModel} setUseProModel={setUseProModel} />}
        </div>
      </main>
      
      <footer className="mt-12 mb-6 text-gray-400 text-[10px] text-center uppercase tracking-widest opacity-50 relative z-0 no-print">
        Powered by Google Gemini • AI Generated Content
      </footer>
    </div>
  );
}

export default App;
