import { clsx } from 'clsx'
import { Check } from 'lucide-react'

interface ProgressBarProps {
  steps: string[]
  currentStep: number
  onStepClick?: (step: number) => void
}

export function ProgressBar({ steps, currentStep, onStepClick }: ProgressBarProps) {
  return (
    <div className="w-full">
      {/* Mobile: simple progress text */}
      <div className="sm:hidden mb-4">
        <div className="flex justify-between text-sm text-gray-500 mb-1">
          <span>Passo {currentStep + 1} de {steps.length}</span>
          <span className="font-medium text-indigo-600">{steps[currentStep]}</span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full">
          <div
            className="h-2 bg-indigo-600 rounded-full transition-all duration-500"
            style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
          />
        </div>
      </div>

      {/* Desktop: step indicators */}
      <div className="hidden sm:flex items-center justify-between relative">
        {/* Line behind steps */}
        <div className="absolute top-4 left-0 right-0 h-0.5 bg-gray-200">
          <div
            className="h-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${(currentStep / (steps.length - 1)) * 100}%` }}
          />
        </div>

        {steps.map((label, index) => {
          const isCompleted = index < currentStep
          const isCurrent = index === currentStep
          const isClickable = index <= currentStep && onStepClick

          return (
            <div key={index} className="flex flex-col items-center relative z-10">
              <button
                type="button"
                onClick={() => isClickable && onStepClick(index)}
                disabled={!isClickable}
                className={clsx(
                  'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-200',
                  isCompleted && 'bg-indigo-600 text-white cursor-pointer hover:bg-indigo-700',
                  isCurrent && 'bg-indigo-600 text-white ring-4 ring-indigo-100',
                  !isCompleted && !isCurrent && 'bg-white border-2 border-gray-300 text-gray-400 cursor-not-allowed'
                )}
              >
                {isCompleted ? <Check size={14} /> : <span>{index + 1}</span>}
              </button>
              <span
                className={clsx(
                  'mt-2 text-xs font-medium whitespace-nowrap',
                  isCurrent ? 'text-indigo-600' : isCompleted ? 'text-gray-600' : 'text-gray-400'
                )}
              >
                {label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
