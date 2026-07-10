import { useState } from 'react'
import { Settings, ChevronDown, ChevronUp } from 'lucide-react'
import { TooltipInfo } from '../ui/TooltipInfo'
import { useAgentWizardStore } from '../../store/agentWizardStore'
import type { SkillConfig } from '../../types/agent'
import { clsx } from 'clsx'

const DEFAULT_SKILLS: SkillConfig[] = [
  {
    id: 'web_search',
    name: 'Pesquisa na Web',
    description: 'Busca informações atualizadas na internet',
    enabled: false,
    icon: '🔍',
    complexity: 'easy',
    requires_config: false,
    config: {},
  },
  {
    id: 'file_reader',
    name: 'Leitura de Arquivos',
    description: 'Lê e interpreta PDFs, Word, Excel e outros',
    enabled: false,
    icon: '📄',
    complexity: 'easy',
    requires_config: false,
    config: {},
  },
  {
    id: 'code_executor',
    name: 'Execução de Código',
    description: 'Executa código Python para cálculos e análises',
    enabled: false,
    icon: '⚡',
    complexity: 'medium',
    requires_config: false,
    config: {},
  },
  {
    id: 'email',
    name: 'Envio de E-mail',
    description: 'Envia e-mails automaticamente',
    enabled: false,
    icon: '📧',
    complexity: 'medium',
    requires_config: true,
    config: { smtp_host: '', smtp_user: '', smtp_pass: '' },
  },
  {
    id: 'calendar',
    name: 'Calendário',
    description: 'Acessa e agenda eventos no Google Calendar',
    enabled: false,
    icon: '📅',
    complexity: 'medium',
    requires_config: true,
    config: { google_credentials: '' },
  },
  {
    id: 'database',
    name: 'Banco de Dados',
    description: 'Consulta e atualiza um banco de dados',
    enabled: false,
    icon: '🗄️',
    complexity: 'hard',
    requires_config: true,
    config: { db_url: '' },
  },
  {
    id: 'image_gen',
    name: 'Geração de Imagens',
    description: 'Cria imagens com inteligência artificial (DALL-E)',
    enabled: false,
    icon: '🎨',
    complexity: 'easy',
    requires_config: false,
    config: {},
  },
  {
    id: 'weather',
    name: 'Previsão do Tempo',
    description: 'Consulta o clima de qualquer cidade',
    enabled: false,
    icon: '🌤️',
    complexity: 'easy',
    requires_config: false,
    config: {},
  },
  {
    id: 'calculator',
    name: 'Calculadora Avançada',
    description: 'Realiza cálculos matemáticos complexos',
    enabled: false,
    icon: '🧮',
    complexity: 'easy',
    requires_config: false,
    config: {},
  },
  {
    id: 'translate',
    name: 'Tradutor',
    description: 'Traduz textos para qualquer idioma',
    enabled: false,
    icon: '🌐',
    complexity: 'easy',
    requires_config: false,
    config: {},
  },
]

const COMPLEXITY_LABELS: Record<string, string> = {
  easy: 'Fácil',
  medium: 'Médio',
  hard: 'Avançado',
}

const SKILL_EXPLANATIONS: Record<string, string> = {
  web_search:
    'Com essa habilidade, seu agente pode pesquisar informações atualizadas na internet, como um assistente que acessa o Google para responder suas perguntas.',
  file_reader:
    'Permite que seu agente leia e entenda arquivos que você enviar, como PDFs de manuais, planilhas Excel ou documentos Word.',
  code_executor:
    'O agente pode escrever e executar código Python para fazer cálculos, analisar dados ou automatizar tarefas.',
  email:
    'Com essa habilidade, seu agente pode enviar e-mails automaticamente. Você precisará configurar as informações do seu servidor de e-mail.',
  calendar:
    'Permite que o agente veja e crie eventos na sua agenda do Google Calendar, como agendar reuniões automaticamente.',
  database:
    'O agente pode consultar e salvar informações em um banco de dados. Requer configuração técnica.',
  image_gen:
    'Seu agente pode criar imagens baseadas em descrições de texto, usando a IA de geração de imagens da OpenAI.',
  weather:
    'O agente pode informar a previsão do tempo de qualquer cidade do mundo em tempo real.',
  calculator:
    'Permite ao agente fazer cálculos matemáticos precisos e resolver equações complexas.',
  translate:
    'O agente pode traduzir textos entre mais de 100 idiomas automaticamente.',
}

interface ConfigFormProps {
  skill: SkillConfig
  onUpdate: (config: Record<string, string>) => void
}

function SkillConfigForm({ skill, onUpdate }: ConfigFormProps) {
  const [localConfig, setLocalConfig] = useState(skill.config ?? {})

  const configFields: Record<string, { label: string; type: string; placeholder: string }[]> = {
    email: [
      { label: 'Servidor SMTP', type: 'text', placeholder: 'smtp.gmail.com' },
      { label: 'E-mail', type: 'email', placeholder: 'seu@email.com' },
      { label: 'Senha / App Password', type: 'password', placeholder: '••••••••' },
    ],
    calendar: [
      {
        label: 'JSON de credenciais Google',
        type: 'textarea',
        placeholder: 'Cole o JSON de credenciais aqui...',
      },
    ],
    database: [
      {
        label: 'URL do Banco de Dados',
        type: 'text',
        placeholder: 'postgresql://usuario:senha@host:5432/banco',
      },
    ],
  }

  const fields = configFields[skill.id] ?? []
  const configKeys = Object.keys(skill.config ?? {})

  function handleChange(key: string, value: string) {
    const updated = { ...localConfig, [key]: value }
    setLocalConfig(updated)
    onUpdate(updated)
  }

  return (
    <div className="mt-3 bg-gray-50 rounded-lg p-4 space-y-3 border border-gray-200">
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
        Configurações obrigatórias
      </p>
      {fields.map((field, idx) => {
        const key = configKeys[idx] ?? `field_${idx}`
        return (
          <div key={key}>
            <label className="block text-sm font-medium text-gray-700 mb-1">{field.label}</label>
            {field.type === 'textarea' ? (
              <textarea
                className="input-field font-mono text-xs"
                rows={3}
                placeholder={field.placeholder}
                value={localConfig[key] ?? ''}
                onChange={(e) => handleChange(key, e.target.value)}
              />
            ) : (
              <input
                type={field.type}
                className="input-field"
                placeholder={field.placeholder}
                value={localConfig[key] ?? ''}
                onChange={(e) => handleChange(key, e.target.value)}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function StepSkills() {
  const { config, updateConfig } = useAgentWizardStore()
  const [expandedConfig, setExpandedConfig] = useState<string | null>(null)

  const skills: SkillConfig[] = config.skills ?? DEFAULT_SKILLS

  function toggleSkill(skillId: string) {
    const updated = skills.map((s) =>
      s.id === skillId ? { ...s, enabled: !s.enabled } : s
    )
    updateConfig({ skills: updated })

    // Auto-expand config if enabling a skill that requires config
    const skill = updated.find((s) => s.id === skillId)
    if (skill?.enabled && skill.requires_config) {
      setExpandedConfig(skillId)
    }
  }

  function updateSkillConfig(skillId: string, newConfig: Record<string, string>) {
    const updated = skills.map((s) =>
      s.id === skillId ? { ...s, config: newConfig } : s
    )
    updateConfig({ skills: updated })
  }

  const enabledCount = skills.filter((s) => s.enabled).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-gray-600 text-base">
          Ative as habilidades que seu agente precisa ter. Você pode ativar quantas quiser!
        </p>
        {enabledCount > 0 && (
          <span className="bg-indigo-100 text-indigo-700 text-sm font-semibold px-3 py-1 rounded-full">
            {enabledCount} ativa{enabledCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="space-y-3">
        {skills.map((skill) => (
          <div
            key={skill.id}
            className={clsx(
              'border-2 rounded-xl transition-all duration-200',
              skill.enabled ? 'border-indigo-300 bg-indigo-50' : 'border-gray-100 bg-white'
            )}
          >
            <div className="flex items-center gap-3 p-4">
              <span className="text-2xl">{skill.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-gray-900">{skill.name}</span>
                  <TooltipInfo text={SKILL_EXPLANATIONS[skill.id] ?? skill.description} />
                  <span
                    className={clsx(
                      'text-xs px-2 py-0.5 rounded-full font-medium',
                      skill.complexity === 'easy' && 'bg-green-100 text-green-700',
                      skill.complexity === 'medium' && 'bg-yellow-100 text-yellow-700',
                      skill.complexity === 'hard' && 'bg-red-100 text-red-700'
                    )}
                  >
                    {COMPLEXITY_LABELS[skill.complexity]}
                  </span>
                </div>
                <p className="text-sm text-gray-500 mt-0.5">{skill.description}</p>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {skill.enabled && skill.requires_config && (
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedConfig(expandedConfig === skill.id ? null : skill.id)
                    }
                    className="text-indigo-500 hover:text-indigo-700 transition-colors"
                    title="Configurar"
                  >
                    <Settings size={16} />
                    {expandedConfig === skill.id ? (
                      <ChevronUp size={14} className="inline ml-0.5" />
                    ) : (
                      <ChevronDown size={14} className="inline ml-0.5" />
                    )}
                  </button>
                )}

                {/* Toggle switch */}
                <button
                  type="button"
                  role="switch"
                  aria-checked={skill.enabled}
                  onClick={() => toggleSkill(skill.id)}
                  className={clsx(
                    'relative w-12 h-6 rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-indigo-400',
                    skill.enabled ? 'bg-indigo-600' : 'bg-gray-300'
                  )}
                >
                  <span
                    className={clsx(
                      'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-300',
                      skill.enabled ? 'translate-x-6' : 'translate-x-0'
                    )}
                  />
                </button>
              </div>
            </div>

            {skill.enabled && skill.requires_config && expandedConfig === skill.id && (
              <div className="px-4 pb-4">
                <SkillConfigForm
                  skill={skill}
                  onUpdate={(cfg) => updateSkillConfig(skill.id, cfg)}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {enabledCount === 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-amber-700 text-sm">
          💡 <strong>Dica:</strong> Você pode prosseguir sem ativar nenhuma habilidade — seu agente
          ainda conseguirá conversar normalmente.
        </div>
      )}
    </div>
  )
}
