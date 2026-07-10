import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Edit2, Play, Download, Trash2, Plus, Calendar } from 'lucide-react'
import { listAgents, deleteAgent } from '../api/agents'
import { useAgentWizardStore } from '../store/agentWizardStore'
import type { AgentConfig } from '../types/agent'

export default function DashboardPage() {
  const { sessionId, resetWizard } = useAgentWizardStore()
  const [agents, setAgents] = useState<AgentConfig[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    loadAgents()
  }, [])

  async function loadAgents() {
    setIsLoading(true)
    try {
      const data = await listAgents(sessionId)
      setAgents(data)
    } catch {
      // Show empty state if API fails
      setAgents([])
    } finally {
      setIsLoading(false)
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm('Tem certeza que deseja excluir este agente? Esta ação não pode ser desfeita.')) {
      return
    }
    setDeletingId(id)
    try {
      await deleteAgent(id)
      setAgents((prev) => prev.filter((a) => a.id !== id))
    } catch {
      alert('Erro ao excluir o agente. Tente novamente.')
    } finally {
      setDeletingId(null)
    }
  }

  const STATUS_LABELS: Record<string, { label: string; color: string }> = {
    draft: { label: 'Rascunho', color: 'bg-gray-100 text-gray-600' },
    ready: { label: 'Pronto', color: 'bg-green-100 text-green-700' },
    paid: { label: 'Pago ✅', color: 'bg-indigo-100 text-indigo-700' },
  }

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="flex flex-col items-center justify-center py-20">
          <div className="text-5xl mb-4 animate-bounce-slow">🤖</div>
          <p className="text-gray-500 font-medium">Carregando seus agentes...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Meus Agentes</h1>
          <p className="text-gray-500 mt-1">
            {agents.length > 0
              ? `Você tem ${agents.length} agente${agents.length !== 1 ? 's' : ''} criado${agents.length !== 1 ? 's' : ''}`
              : 'Nenhum agente criado ainda'}
          </p>
        </div>
        <Link
          to="/wizard"
          onClick={resetWizard}
          className="flex items-center gap-2 btn-primary"
        >
          <Plus size={18} />
          Novo Agente
        </Link>
      </div>

      {/* Agents grid */}
      {agents.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {agents.map((agent) => {
            const persona = agent.persona
            const statusInfo = STATUS_LABELS[agent.status ?? 'draft']

            return (
              <div key={agent.id} className="card hover:shadow-md transition-shadow flex flex-col">
                {/* Header */}
                <div className="flex items-start gap-4 mb-4">
                  <div className="w-14 h-14 bg-indigo-100 rounded-2xl flex items-center justify-center text-3xl shrink-0">
                    {persona?.avatar_emoji ?? '🤖'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="font-bold text-gray-900 text-lg truncate">
                        {persona?.name ?? 'Agente sem nome'}
                      </h3>
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded-full shrink-0 ${statusInfo.color}`}
                      >
                        {statusInfo.label}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {agent.characteristics?.role_label ?? 'Assistente'}
                    </p>
                  </div>
                </div>

                {/* Details */}
                <div className="space-y-2 mb-4 flex-1">
                  {agent.framework && (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <span>{agent.framework.icon}</span>
                      <span>{agent.framework.name}</span>
                    </div>
                  )}
                  {agent.model && (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <span>🧠</span>
                      <span>{agent.model.model_name}</span>
                    </div>
                  )}
                  {agent.created_at && (
                    <div className="flex items-center gap-2 text-xs text-gray-400">
                      <Calendar size={12} />
                      <span>
                        Criado em{' '}
                        {new Date(agent.created_at).toLocaleDateString('pt-BR', {
                          day: '2-digit',
                          month: '2-digit',
                          year: 'numeric',
                        })}
                      </span>
                    </div>
                  )}

                  {/* Enabled skills */}
                  {agent.skills && agent.skills.filter((s) => s.enabled).length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {agent.skills
                        .filter((s) => s.enabled)
                        .slice(0, 3)
                        .map((s) => (
                          <span
                            key={s.id}
                            className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full"
                          >
                            {s.icon} {s.name}
                          </span>
                        ))}
                      {agent.skills.filter((s) => s.enabled).length > 3 && (
                        <span className="text-xs text-gray-400">
                          +{agent.skills.filter((s) => s.enabled).length - 3} mais
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-2 pt-3 border-t border-gray-100">
                  <Link
                    to={`/wizard/${agent.id}`}
                    className="flex-1 flex items-center justify-center gap-1.5 text-sm font-medium text-indigo-600 border border-indigo-200 py-2 rounded-xl hover:bg-indigo-50 transition-colors"
                  >
                    <Edit2 size={14} />
                    Editar
                  </Link>
                  <Link
                    to={`/test/${agent.id}`}
                    className="flex-1 flex items-center justify-center gap-1.5 text-sm font-medium text-green-600 border border-green-200 py-2 rounded-xl hover:bg-green-50 transition-colors"
                  >
                    <Play size={14} />
                    Testar
                  </Link>
                  <button
                    type="button"
                    title="Baixar agente"
                    className="flex items-center justify-center w-10 text-gray-400 border border-gray-200 rounded-xl hover:bg-gray-50 hover:text-indigo-600 transition-colors"
                  >
                    <Download size={14} />
                  </button>
                  <button
                    type="button"
                    title="Excluir agente"
                    onClick={() => agent.id && handleDelete(agent.id)}
                    disabled={deletingId === agent.id}
                    className="flex items-center justify-center w-10 text-gray-400 border border-gray-200 rounded-xl hover:bg-red-50 hover:text-red-500 hover:border-red-200 transition-colors disabled:opacity-50"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        /* Empty state */
        <div className="text-center py-20 bg-white rounded-2xl border border-gray-100 shadow-sm">
          <div className="text-7xl mb-5">🤖</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-3">
            Você ainda não criou nenhum agente.
          </h2>
          <p className="text-gray-500 text-lg mb-8 max-w-sm mx-auto">
            Que tal criar seu primeiro agente de IA agora? Leva menos de 10 minutos!
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/wizard" onClick={resetWizard} className="btn-primary inline-flex items-center gap-2">
              <Plus size={18} />
              Criar meu primeiro Agente →
            </Link>
            <Link to="/templates" className="btn-secondary inline-flex items-center gap-2">
              Ver templates prontos
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
