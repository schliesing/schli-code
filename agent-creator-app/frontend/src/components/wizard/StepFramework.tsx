import { useState } from 'react'
import { ChevronDown, ChevronUp, Plus } from 'lucide-react'
import { StepCard } from '../ui/StepCard'
import { TooltipInfo } from '../ui/TooltipInfo'
import { useAgentWizardStore } from '../../store/agentWizardStore'
import type { FrameworkConfig } from '../../types/agent'

const FRAMEWORKS: FrameworkConfig[] = [
  {
    id: 'langchain',
    name: 'LangChain',
    description: 'O mais popular para criar agentes de IA',
    beginner_explanation:
      'LangChain é como uma caixa de ferramentas completa para construir agentes de IA. É a escolha mais popular e tem muito suporte da comunidade. Perfeito para quem está começando!',
    recommended: true,
    icon: '⛓️',
  },
  {
    id: 'langgraph',
    name: 'LangGraph',
    description: 'Para agentes com fluxos de trabalho complexos',
    beginner_explanation:
      'LangGraph permite criar agentes que podem tomar decisões mais elaboradas, como se fosse um fluxograma de ações. Ideal quando você quer que seu agente siga etapas específicas.',
    recommended: false,
    icon: '🕸️',
  },
  {
    id: 'crewai',
    name: 'CrewAI',
    description: 'Equipes de agentes trabalhando juntos',
    beginner_explanation:
      'CrewAI cria "equipes" de agentes de IA, onde cada agente tem um papel específico, como um time de funcionários. Ótimo quando você precisa que vários agentes colaborem.',
    recommended: false,
    icon: '👥',
  },
  {
    id: 'autogen',
    name: 'AutoGen',
    description: 'Agentes que conversam entre si para resolver problemas',
    beginner_explanation:
      'AutoGen da Microsoft faz agentes conversarem entre si até resolver uma tarefa. Como ter dois especialistas discutindo um problema até encontrar a melhor solução.',
    recommended: false,
    icon: '🤝',
  },
  {
    id: 'openai-assistants',
    name: 'OpenAI Assistants',
    description: 'API oficial da OpenAI para assistentes',
    beginner_explanation:
      'A própria OpenAI (criadora do ChatGPT) oferece essa plataforma para criar assistentes. Muito simples de usar, mas requer uma conta na OpenAI.',
    recommended: false,
    icon: '🧠',
  },
  {
    id: 'pydantic-ai',
    name: 'PydanticAI',
    description: 'Framework moderno com tipagem forte',
    beginner_explanation:
      'PydanticAI é um framework mais novo que garante que as respostas do agente tenham sempre o formato correto. Ideal para desenvolvedores que gostam de código organizado.',
    recommended: false,
    icon: '🐍',
  },
]

export function StepFramework() {
  const { config, updateConfig } = useAgentWizardStore()
  const [showCustomForm, setShowCustomForm] = useState(false)
  const [customCode, setCustomCode] = useState('')
  const [customName, setCustomName] = useState('')

  const selectedId = config.framework?.id

  function handleSelect(fw: FrameworkConfig) {
    updateConfig({ framework: fw })
  }

  function handleAddCustom() {
    if (!customName.trim()) return
    const custom: FrameworkConfig = {
      id: `custom-${Date.now()}`,
      name: customName,
      description: 'Framework personalizado',
      beginner_explanation: 'Você adicionou um framework personalizado.',
      recommended: false,
      icon: '⚙️',
      custom: true,
      custom_code: customCode,
    }
    updateConfig({ framework: custom })
    setShowCustomForm(false)
    setCustomName('')
    setCustomCode('')
  }

  return (
    <div className="space-y-4">
      <p className="text-gray-600 text-base">
        O framework é a "fundação" do seu agente — como a base de uma casa. Escolha um abaixo:
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {FRAMEWORKS.map((fw) => (
          <StepCard
            key={fw.id}
            selected={selectedId === fw.id}
            onClick={() => handleSelect(fw)}
            badge={fw.recommended ? '⭐ Para iniciantes' : undefined}
          >
            <div className="flex items-start gap-3 pt-1">
              <span className="text-3xl">{fw.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1">
                  <h3 className="font-semibold text-gray-900">{fw.name}</h3>
                  <TooltipInfo text={fw.beginner_explanation} />
                </div>
                <p className="text-sm text-gray-500 mt-0.5">{fw.description}</p>
              </div>
            </div>
          </StepCard>
        ))}
      </div>

      {/* Custom framework collapsible */}
      <div className="border border-dashed border-gray-300 rounded-xl overflow-hidden">
        <button
          type="button"
          onClick={() => setShowCustomForm(!showCustomForm)}
          className="w-full flex items-center justify-between px-5 py-4 text-gray-600 hover:text-indigo-600 hover:bg-gray-50 transition-colors"
        >
          <span className="flex items-center gap-2 font-medium">
            <Plus size={18} />
            Adicionar framework personalizado
          </span>
          {showCustomForm ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>

        {showCustomForm && (
          <div className="px-5 pb-5 space-y-3 border-t border-gray-100 pt-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Nome do framework
              </label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                className="input-field"
                placeholder="Ex: Meu Framework Personalizado"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Código de inicialização (opcional)
              </label>
              <textarea
                value={customCode}
                onChange={(e) => setCustomCode(e.target.value)}
                className="input-field font-mono text-sm"
                rows={4}
                placeholder="# Cole o código de inicialização do seu framework aqui"
              />
            </div>
            <button
              type="button"
              onClick={handleAddCustom}
              disabled={!customName.trim()}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Adicionar
            </button>
          </div>
        )}
      </div>

      {selectedId && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-green-700 text-sm font-medium">
          ✅ Framework selecionado:{' '}
          {FRAMEWORKS.find((f) => f.id === selectedId)?.name ?? config.framework?.name}
        </div>
      )}
    </div>
  )
}
