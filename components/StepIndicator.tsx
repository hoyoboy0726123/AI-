
import React from 'react';

interface StepIndicatorProps {
  currentStep: number;
  onStepClick?: (stepId: number) => void;
}

const steps = [
  { id: 1, name: '設定地基' },
  { id: 2, name: '空間拼圖' },
  { id: 3, name: '選擇風格' },
  { id: 4, name: '完成設計' },
];

export const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep, onStepClick }) => {
  return (
    <div className="flex justify-between items-center w-full max-w-lg mx-auto mb-8 relative">
      <div className="absolute top-1/2 left-0 w-full h-1 bg-gray-200 -z-10 rounded-full"></div>
      <div 
        className="absolute top-1/2 left-0 h-1 bg-blue-600 -z-10 rounded-full transition-all duration-500 ease-out"
        style={{ width: `${((currentStep - 1) / (steps.length - 1)) * 100}%` }}
      ></div>
      
      {steps.map((step) => {
        const isActive = step.id === currentStep;
        const isCompleted = step.id < currentStep;
        const isClickable = onStepClick && (isCompleted || isActive);

        return (
          <div key={step.id} className="flex flex-col items-center bg-white px-2">
            <button 
              onClick={() => {
                if (onStepClick) onStepClick(step.id);
              }}
              disabled={!onStepClick}
              className={`
                w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-all duration-300
                ${isActive ? 'border-blue-600 bg-blue-600 text-white scale-110' : 
                  isCompleted ? 'border-blue-600 bg-white text-blue-600 hover:bg-blue-50 cursor-pointer' : 'border-gray-300 bg-white text-gray-400 cursor-not-allowed'}
              `}
            >
              {isCompleted ? '✓' : step.id}
            </button>
            <span className={`text-xs mt-2 font-medium ${isActive || isCompleted ? 'text-blue-800' : 'text-gray-400'}`}>
              {step.name}
            </span>
          </div>
        );
      })}
    </div>
  );
};
