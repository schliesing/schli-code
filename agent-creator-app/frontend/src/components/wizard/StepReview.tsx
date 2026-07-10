import { useNavigate } from 'react-router-dom'
import { Edit2, ExternalLink, Download, Save, CheckCircle } from 'lucide-react'
import { useAgentWizardStore } from '../../store/agentWizardStore'

interface ReviewSectionProps {
  title: string
  icon: string
  step: number
  onEdit: (step: number) => void
  children: React.ReactNode
}

function ReviewSection({ title, icon, step, onEdit, children }: ReviewSectionProps) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">{icon}</span>
          <h3 className="font-semibold text-gray-900">{title}</h3>
        </div>
        <button
          type="button"
          onClick={() => onEdit(step)}
          className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800 font-medium border border-indigo-200 px-2.5 py-1 rounded-lg hover:bg-indigo-50 transition-colors"
        >
          <Edit2 size={12} />
          Editar
        </button>
      </div>
      {children}
    </div>
  )
}

export function StepReview() {
  const navigate = useNavigate()
  const { config, agentId, setStep } = useAgentWizardStore()

  const persona = config.persona
  const framework = config.framework
  const characteristics = config.characteristics
  const skills = config.skills ?? []
  const model = config.model
  const memory = config.memory
  const deployment = config.deployment

  const enabledSkills = skills.filter((s) => s.enabled)
  const enabledTargets = deployment?.targets.filter((t) => t.enabled) ?? []

  const MEMORY_LABELS: Record<string, string> = {
    none: '🧠 Sem Memória',
    buffer: '💬 Memória Simples',
    semantic: '🔍 Memória Semântica',
    document: '📚 Memória com Documentos',
  }

  const TONE_LABELS: Record<string, string> = {
    professional: 'Profissional 👔',
    friendly: 'Amigável 😊',
    casual: 'Descontraído 😎',
    direct: 'Direto ao ponto ⚡',
  }

  function handleTest() {
    if (agentId) {
      window.open(`/test/${agentId}`, '_blank')
    }
  }

  function handleSaveDraft() {
    // Agent is auto-saved, just show feedback
    alert('✅ Rascunho salvo com sucesso!')
  }

  function handlePayment() {
    // Redirect to payment flow
    navigate(`/payment/success?agent_id=${agentId}`)
  }

  const isComplete = framework && characteristics && model && memory && persona

  return (
    <div className="space-y-5">
      {isComplete ? (
        <div className="bg-green-50 border border-green-200 rounded-xl px-5 py-4 flex items-center gap-3">
          <CheckCircle className="text-green-600 shrink-0" size={24} />
          <div>
            <p className="font-semibold text-green-900">Seu agente está configurado!</p>
            <p className="text-sm text-green-700">
              Revise as configurações abaixo e teste seu agente antes de baixar.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 text-amber-800">
          <p className="font-semibold">⚠️ Algumas configurações estão incompletas</p>
          <p className="text-sm mt-1">
            Revise os passos anteriores para garantir que tudo está preenchido.
          </p>
        </div>
      )}

      {/* Agent identity card */}
      {persona && (
        <div className="bg-gradient-to-r from-indigo-600 to-purple-600 rounded-xl p-6 text-white">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center text-4xl">
              {persona.avatar_emoji}
            </div>
            <div>
              <h2 className="text-2xl font-bold">{persona.name || 'Meu Agente'}</h2>
              <p className="text-indigo-100 text-sm mt-1">
                {characteristics?.role_label ?? 'Assistente'}
              </p>
            </div>
          </div>
          {persona.greeting && (
            <div className="mt-4 bg-white/10 rounded-xl p-3 text-sm">
              <span className="text-indigo-200 text-xs block mb-1">Mensagem de boas-vindas:</span>
              <p>"{persona.greeting}"</p>
            </div>
          )}
        </div>
      )}

      {/* Review sections */}
      <div className="space-y-3">
        <ReviewSection title="Framework" icon="⛓️" step={0} onEdit={setStep}>
          {framework ? (
            <div className="flex items-center gap-2">
              <span className="text-xl">{framework.icon}</span>
              <span className="font-medium text-gray-800">{framework.name}</span>
              {framework.recommended && (
                <span className="badge-beginner">Para iniciantes</span>
              )}
            </div>
          ) : (
            <p className="text-red-500 text-sm">⚠️ Não configurado</p>
          )}
        </ReviewSection>

        <ReviewSection title="Tipo de agente" icon="🎯" step={1} onEdit={setStep}>
          {characteristics ? (
            <div>
              <p className="font-medium text-gray-800">{characteristics.role_label}</p>
              {characteristics.multi_agent && (
                <p className="text-sm text-indigo-600 mt-1">
                  👥 Com sub-agentes: {characteristics.sub_agent_roles?.join(', ')}
                </p>
              )}
            </div>
          ) : (
            <p className="text-red-500 text-sm">⚠️ Não configurado</p>
          )}
        </ReviewSection>

        <ReviewSection title="Habilidades" icon="⚡" step={2} onEdit={setStep}>
          {enabledSkills.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {enabledSkills.map((s) => (
                <span
                  key={s.id}
                  className="flex items-center gap-1 bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-full text-sm"
                >
                  {s.icon} {s.name}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Nenhuma habilidade extra ativada (conversas básicas)</p>
          )}
        </ReviewSection>

        <ReviewSection title="Modelo de IA" icon="🧠" step={3} onEdit={setStep}>
          {model ? (
            <div className="flex items-center gap-3">
              <div>
                <p className="font-medium text-gray-800">{model.model_name}</p>
                <p className="text-sm text-gray-500">
                  {model.provider} • {model.local ? 'Local (gratuito)' : 'Na nuvem'}
                </p>
                {!model.local && model.api_key && (
                  <p className="text-xs text-green-600 mt-0.5">✅ Chave API configurada</p>
                )}
                {!model.local && !model.api_key && (
                  <p className="text-xs text-amber-600 mt-0.5">⚠️ Chave API não informada</p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-red-500 text-sm">⚠️ Não configurado</p>
          )}
        </ReviewSection>

        <ReviewSection title="Memória" icon="💾" step={4} onEdit={setStep}>
          {memory ? (
            <p className="font-medium text-gray-800">
              {MEMORY_LABELS[memory.type] ?? memory.type}
            </p>
          ) : (
            <p className="text-red-500 text-sm">⚠️ Não configurado</p>
          )}
        </ReviewSection>

        <ReviewSection title="Personalidade" icon="✨" step={5} onEdit={setStep}>
          {persona ? (
            <div className="space-y-1">
              <p className="text-sm text-gray-600">
                <span className="font-medium">Tom:</span>{' '}
                {TONE_LABELS[persona.tone] ?? persona.tone}
              </p>
              <p className="text-sm text-gray-600">
                <span className="font-medium">Idioma:</span> {persona.language}
              </p>
              {persona.system_prompt && (
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                  {persona.system_prompt.substring(0, 100)}
                  {persona.system_prompt.length > 100 ? '...' : ''}
                </p>
              )}
            </div>
          ) : (
            <p className="text-red-500 text-sm">⚠️ Não configurado</p>
          )}
        </ReviewSection>

        <ReviewSection title="Deploy" icon="🚀" step={6} onEdit={setStep}>
          {enabledTargets.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {enabledTargets.map((t) => {
                const icons: Record<string, string> = {
                  telegram: '📱 Telegram',
                  discord: '🎮 Discord',
                  api: '🌐 API REST',
                  widget: '🖥️ Widget',
                  whatsapp: '💬 WhatsApp',
                }
                return (
                  <span
                    key={t.type}
                    className="bg-purple-50 text-purple-700 px-2.5 py-1 rounded-full text-sm"
                  >
                    {icons[t.type] ?? t.type}
                  </span>
                )
              })}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">Nenhum destino configurado ainda</p>
          )}
        </ReviewSection>
      </div>

      {/* Action buttons */}
      <div className="flex flex-col gap-3 pt-2">
        <button
          type="button"
          onClick={handleTest}
          disabled={!agentId}
          className="flex items-center justify-center gap-2 w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-4 rounded-xl transition-colors shadow-sm hover:shadow-md text-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ExternalLink size={20} />
          🧪 Testar meu Agente
        </button>

        <button
          type="button"
          onClick={handlePayment}
          disabled={!agentId || !isComplete}
          className="flex items-center justify-center gap-2 w-full bg-green-600 hover:bg-green-700 text-white font-bold py-4 rounded-xl transition-colors shadow-sm hover:shadow-md text-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Download size={20} />
          📦 Baixar meu Agente — R$ 9,99
        </button>

        <button
          type="button"
          onClick={handleSaveDraft}
          className="flex items-center justify-center gap-2 w-full bg-white hover:bg-gray-50 text-gray-700 font-semibold py-3 rounded-xl border border-gray-200 transition-colors"
        >
          <Save size={18} />
          Salvar Rascunho
        </button>
      </div>
    </div>
  )
}
