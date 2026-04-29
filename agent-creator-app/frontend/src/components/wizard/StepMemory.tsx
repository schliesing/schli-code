import { TooltipInfo } from '../ui/TooltipInfo'
import { useAgentWizardStore } from '../../store/agentWizardStore'
import type { MemoryConfig } from '../../types/agent'

interface MemoryOption {
  type: MemoryConfig['type']
  icon: string
  title: string
  description: string
  detail: string
  beginner_explanation: string
  recommended?: boolean
  color: ColorKey
}

const MEMORY_OPTIONS: MemoryOption[] = [
  {
    type: 'none',
    icon: '🧠',
    title: 'Sem Memória',
    description: 'Esquece tudo após cada conversa',
    detail: 'Como falar com alguém com amnésia — cada conversa começa do zero, sem lembrar nada anterior.',
    beginner_explanation:
      'Sem memória, seu agente não lembrará de nenhuma conversa anterior. É o mais simples e funciona bem para consultas pontuais onde o histórico não importa.',
    recommended: false,
    color: 'gray',
  },
  {
    type: 'buffer',
    icon: '💬',
    title: 'Memória Simples',
    description: 'Lembra da conversa atual',
    detail: 'O agente se lembra de tudo que foi dito dentro da mesma conversa, mas esquece ao reiniciar.',
    beginner_explanation:
      'A memória simples guarda o histórico da conversa atual. É como o ChatGPT — o agente lembra do que você disse antes na mesma sessão, mas esquece quando você fecha e abre novamente.',
    recommended: true,
    color: 'indigo',
  },
  {
    type: 'semantic',
    icon: '🔍',
    title: 'Memória Semântica',
    description: 'Entende contexto de conversas anteriores',
    detail: 'Guarda e recupera memórias de conversas passadas, entendendo o significado e contexto.',
    beginner_explanation:
      'A memória semântica permite que seu agente se lembre de conversas passadas de forma inteligente. Ele não apenas lembra o texto, mas entende o significado. Como um amigo que realmente presta atenção no que você conta.',
    recommended: false,
    color: 'purple',
  },
  {
    type: 'document',
    icon: '📚',
    title: 'Memória com Documentos',
    description: 'Lê seus arquivos e responde baseado neles',
    detail: 'Pode ler PDFs, Word, Excel e responder perguntas baseadas no conteúdo dos seus documentos.',
    beginner_explanation:
      'Com esta memória, você pode "alimentar" seu agente com documentos como manuais, relatórios ou contratos. Ele lerá tudo e poderá responder perguntas baseadas no conteúdo — como um funcionário que estudou todos os documentos da empresa.',
    recommended: false,
    color: 'green',
  },
]

type ColorKey = 'gray' | 'indigo' | 'purple' | 'green'

const COLOR_CLASSES: Record<ColorKey, { border: string; bg: string; icon: string; text: string }> = {
  gray: { border: 'border-gray-200', bg: 'bg-gray-50', icon: 'bg-gray-100', text: 'text-gray-600' },
  indigo: { border: 'border-indigo-200', bg: 'bg-indigo-50', icon: 'bg-indigo-100', text: 'text-indigo-600' },
  purple: { border: 'border-purple-200', bg: 'bg-purple-50', icon: 'bg-purple-100', text: 'text-purple-600' },
  green: { border: 'border-green-200', bg: 'bg-green-50', icon: 'bg-green-100', text: 'text-green-600' },
}

export function StepMemory() {
  const { config, updateConfig } = useAgentWizardStore()
  const selectedType = config.memory?.type

  function handleSelect(option: MemoryOption) {
    const mem: MemoryConfig = {
      type: option.type,
    }
    if (option.type === 'semantic') {
      mem.vector_store = 'chroma'
    }
    updateConfig({ memory: mem })
  }

  return (
    <div className="space-y-4">
      <p className="text-gray-600 text-base">
        A memória define como seu agente lembra das conversas. Escolha o tipo que melhor se encaixa
        na sua necessidade:
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {MEMORY_OPTIONS.map((option) => {
          const colors = COLOR_CLASSES[option.color]
          const isSelected = selectedType === option.type

          return (
            <button
              key={option.type}
              type="button"
              onClick={() => handleSelect(option)}
              className={`text-left p-5 rounded-xl border-2 transition-all duration-200 hover:shadow-md relative ${
                isSelected
                  ? 'border-indigo-500 bg-indigo-50 ring-2 ring-indigo-200 shadow-md'
                  : `${colors.border} bg-white hover:border-indigo-300`
              }`}
            >
              {option.recommended && (
                <span className="absolute top-3 right-3 badge-beginner">
                  ⭐ Recomendado
                </span>
              )}

              <div className={`w-14 h-14 ${colors.bg} rounded-xl flex items-center justify-center text-3xl mb-3`}>
                {option.icon}
              </div>

              <div className="flex items-center gap-1 mb-1">
                <h3 className="font-bold text-gray-900 text-lg">{option.title}</h3>
                <TooltipInfo text={option.beginner_explanation} />
              </div>

              <p className={`text-sm font-medium ${colors.text} mb-2`}>{option.description}</p>
              <p className="text-sm text-gray-500 leading-relaxed">{option.detail}</p>

              {isSelected && (
                <div className="mt-3 text-xs text-indigo-600 font-semibold">✅ Selecionado</div>
              )}
            </button>
          )
        })}
      </div>

      {selectedType === 'document' && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800 animate-fade-in">
          <p className="font-semibold mb-1">📄 Sobre a Memória com Documentos</p>
          <p>
            Você poderá adicionar seus documentos após criar o agente. Formatos suportados: PDF,
            Word (.docx), Excel (.xlsx), TXT e Markdown.
          </p>
        </div>
      )}

      {selectedType === 'semantic' && (
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 text-sm text-purple-800 animate-fade-in">
          <p className="font-semibold mb-1">🔍 Sobre a Memória Semântica</p>
          <p>
            Usará ChromaDB como banco de vetores para armazenar e recuperar memórias de forma
            inteligente. Configurado automaticamente!
          </p>
        </div>
      )}
    </div>
  )
}
