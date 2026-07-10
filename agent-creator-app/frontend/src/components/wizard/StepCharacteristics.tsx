import { useState } from 'react'
import { StepCard } from '../ui/StepCard'
import { TooltipInfo } from '../ui/TooltipInfo'
import { useAgentWizardStore } from '../../store/agentWizardStore'
import type { CharacteristicConfig } from '../../types/agent'

interface RoleOption {
  id: string
  label: string
  icon: string
  description: string
  use_cases: string[]
  beginner_explanation: string
  isOrchestrator?: boolean
}

const ROLES: RoleOption[] = [
  {
    id: 'assistant',
    label: 'Assistente Geral',
    icon: '🙋',
    description: 'Responde perguntas e ajuda com tarefas diversas',
    use_cases: ['Responder dúvidas', 'Gerar textos e resumos', 'Auxiliar em tarefas do dia a dia'],
    beginner_explanation:
      'Um assistente geral é como um ajudante versátil que pode responder perguntas, escrever textos e ajudar com diversas tarefas. É o papel mais comum e fácil de começar.',
  },
  {
    id: 'customer_service',
    label: 'Atendimento ao Cliente',
    icon: '💁',
    description: 'Atende clientes, responde dúvidas sobre produtos e serviços',
    use_cases: [
      'Responder perguntas frequentes',
      'Registrar reclamações',
      'Informar sobre produtos',
    ],
    beginner_explanation:
      'Um agente de atendimento ao cliente é como um atendente virtual 24 horas que nunca cansa. Ele responde dúvidas dos seus clientes automaticamente.',
  },
  {
    id: 'coder',
    label: 'Assistente de Programação',
    icon: '👨‍💻',
    description: 'Ajuda a escrever, revisar e explicar código',
    use_cases: [
      'Gerar código em várias linguagens',
      'Explicar erros e soluções',
      'Revisar código existente',
    ],
    beginner_explanation:
      'Um assistente de programação é como ter um programador experiente sempre disponível para te ajudar a escrever código, encontrar erros e aprender novas tecnologias.',
  },
  {
    id: 'researcher',
    label: 'Pesquisador',
    icon: '🔬',
    description: 'Pesquisa, coleta e sintetiza informações',
    use_cases: ['Pesquisar na internet', 'Resumir documentos', 'Comparar informações'],
    beginner_explanation:
      'Um agente pesquisador é como um assistente de pesquisa que vasculha a internet e documentos para encontrar as informações que você precisa, resumindo tudo de forma clara.',
  },
  {
    id: 'data_analyst',
    label: 'Analista de Dados',
    icon: '📊',
    description: 'Analisa dados, cria gráficos e encontra padrões',
    use_cases: [
      'Analisar planilhas e tabelas',
      'Identificar tendências',
      'Gerar relatórios automáticos',
    ],
    beginner_explanation:
      'Um analista de dados automatiza a análise de planilhas e bases de dados, encontrando insights importantes sem que você precise ser especialista em estatística.',
  },
  {
    id: 'orchestrator',
    label: 'Coordenador de Agentes',
    icon: '🎯',
    description: 'Gerencia outros agentes especializados para tarefas complexas',
    use_cases: [
      'Dividir tarefas complexas entre agentes',
      'Coordenar fluxos de trabalho',
      'Combinar resultados de múltiplos agentes',
    ],
    beginner_explanation:
      'Um coordenador é como um gerente que distribui tarefas para uma equipe de agentes especializados. Cada agente faz uma parte do trabalho e o coordenador junta tudo.',
    isOrchestrator: true,
  },
]

const SUB_AGENT_OPTIONS = ['Pesquisador', 'Programador', 'Analista', 'Redator', 'Revisor']

export function StepCharacteristics() {
  const { config, updateConfig } = useAgentWizardStore()
  const [subAgentRoles, setSubAgentRoles] = useState<string[]>(
    config.characteristics?.sub_agent_roles ?? []
  )

  const selectedRole = config.characteristics?.role

  function handleRoleSelect(role: RoleOption) {
    const char: CharacteristicConfig = {
      role: role.id,
      role_label: role.label,
      use_cases: role.use_cases,
      multi_agent: role.isOrchestrator ?? false,
      sub_agent_roles: role.isOrchestrator ? subAgentRoles : [],
    }
    updateConfig({ characteristics: char })
  }

  function toggleSubAgent(name: string) {
    const updated = subAgentRoles.includes(name)
      ? subAgentRoles.filter((r) => r !== name)
      : [...subAgentRoles, name]
    setSubAgentRoles(updated)
    if (config.characteristics) {
      updateConfig({
        characteristics: { ...config.characteristics, sub_agent_roles: updated },
      })
    }
  }

  const isOrchestrator = selectedRole === 'orchestrator'

  return (
    <div className="space-y-4">
      <p className="text-gray-600 text-base">
        Qual é o papel principal do seu agente? Isso define o que ele faz melhor.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {ROLES.map((role) => (
          <StepCard
            key={role.id}
            selected={selectedRole === role.id}
            onClick={() => handleRoleSelect(role)}
            badge={role.id === 'assistant' ? '⭐ Recomendado' : undefined}
          >
            <div className="flex items-start gap-3 pt-1">
              <span className="text-3xl">{role.icon}</span>
              <div className="flex-1">
                <div className="flex items-center gap-1">
                  <h3 className="font-semibold text-gray-900">{role.label}</h3>
                  <TooltipInfo text={role.beginner_explanation} />
                </div>
                <p className="text-sm text-gray-500 mt-0.5">{role.description}</p>
                <ul className="mt-2 space-y-0.5">
                  {role.use_cases.map((uc) => (
                    <li key={uc} className="text-xs text-gray-400 flex items-start gap-1">
                      <span className="text-indigo-400 mt-0.5">•</span>
                      {uc}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </StepCard>
        ))}
      </div>

      {/* Multi-agent sub-roles */}
      {isOrchestrator && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 space-y-3 animate-fade-in">
          <div className="flex items-center gap-2">
            <span className="text-xl">👥</span>
            <h4 className="font-semibold text-indigo-900">Sub-agentes da equipe</h4>
            <TooltipInfo text="Escolha quais tipos de agentes vão compor sua equipe. Cada sub-agente é especializado em uma área." />
          </div>
          <p className="text-sm text-indigo-700">
            Quais especialistas fazem parte da sua equipe de agentes?
          </p>
          <div className="flex flex-wrap gap-2">
            {SUB_AGENT_OPTIONS.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => toggleSubAgent(name)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                  subAgentRoles.includes(name)
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white text-indigo-600 border border-indigo-300 hover:border-indigo-500'
                }`}
              >
                {name}
              </button>
            ))}
          </div>
          {subAgentRoles.length > 0 && (
            <p className="text-xs text-indigo-600">
              ✅ Equipe: {subAgentRoles.join(', ')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
