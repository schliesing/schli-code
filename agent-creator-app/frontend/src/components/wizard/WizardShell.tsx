import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Save } from 'lucide-react'
import { ProgressBar } from '../ui/ProgressBar'
import { useAgentWizardStore } from '../../store/agentWizardStore'

const STEP_LABELS = [
  'Estrutura',
  'Tipo',
  'Habilidades',
  'Modelo IA',
  'Memória',
  'Personalidade',
  'Deploy',
  'Revisão',
]

const STEP_ENCOURAGEMENTS = [
  'Vamos começar! Escolha como seu agente vai funcionar.',
  'Ótimo! Agora defina o papel do seu agente.',
  'Excelente! Quais superpoderes seu agente terá?',
  'Perfeito! Escolha o cérebro do seu agente.',
  'Incrível! Como seu agente vai se lembrar das coisas?',
  'Quase lá! Dê uma personalidade ao seu agente.',
  'Ótimo trabalho! Onde seu agente vai atuar?',
  'Uau! Revise tudo e prepare-se para testar!',
]

interface WizardShellProps {
  children: ReactNode
  onNext: () => void
  onBack: () => void
  canProceed?: boolean
  isLastStep?: boolean
  isLoading?: boolean
  lastSavedAt?: string | null
}

export function WizardShell({
  children,
  onNext,
  onBack,
  canProceed = true,
  isLastStep = false,
  isLoading = false,
  lastSavedAt,
}: WizardShellProps) {
  const { currentStep, setStep } = useAgentWizardStore()

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 shadow-sm sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <Link to="/" className="flex items-center gap-2 text-indigo-600 font-bold text-lg">
              <span className="text-2xl">🤖</span>
              <span>CriaBot</span>
            </Link>
            <div className="flex items-center gap-3">
              {lastSavedAt && (
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <Save size={12} />
                  Salvo automaticamente
                </span>
              )}
            </div>
          </div>
          <ProgressBar
            steps={STEP_LABELS}
            currentStep={currentStep}
            onStepClick={(step) => step < currentStep && setStep(step)}
          />
        </div>
      </header>

      {/* Encouragement message */}
      <div className="max-w-4xl mx-auto w-full px-4 sm:px-6 pt-6">
        <p className="text-indigo-600 font-medium text-sm">
          {STEP_ENCOURAGEMENTS[currentStep]}
        </p>
        <h2 className="text-2xl font-bold text-gray-900 mt-1">
          {STEP_LABELS[currentStep]}
        </h2>
      </div>

      {/* Content */}
      <main className="flex-1 max-w-4xl mx-auto w-full px-4 sm:px-6 py-6 animate-slide-up">
        {children}
      </main>

      {/* Footer navigation */}
      <div className="sticky bottom-0 bg-white border-t border-gray-100 shadow-lg">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <button
            type="button"
            onClick={onBack}
            disabled={currentStep === 0}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 font-medium disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ArrowLeft size={18} />
            Voltar
          </button>

          <span className="text-sm text-gray-400">
            {currentStep + 1} / {STEP_LABELS.length}
          </span>

          {!isLastStep && (
            <button
              type="button"
              onClick={onNext}
              disabled={isLoading}
              className={`flex items-center gap-2 font-semibold px-6 py-2.5 rounded-xl transition-all duration-200 shadow-sm ${
                canProceed
                  ? 'bg-indigo-600 hover:bg-indigo-700 text-white hover:shadow-md'
                  : 'bg-indigo-200 text-indigo-400 cursor-pointer hover:bg-indigo-300'
              } ${isLoading ? 'opacity-70 cursor-wait' : ''}`}
            >
              {isLoading ? 'Salvando...' : 'Próximo →'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
