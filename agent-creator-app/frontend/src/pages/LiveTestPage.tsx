import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, RotateCcw, Wifi, WifiOff, Download } from 'lucide-react'
import { ChatWindow } from '../components/chat/ChatWindow'
import { ChatInput } from '../components/chat/ChatInput'
import { useChatSocket } from '../hooks/useChatSocket'
import { useAgentWizardStore } from '../store/agentWizardStore'
import { getAgent } from '../api/agents'
import type { AgentConfig } from '../types/agent'

export default function LiveTestPage() {
  const { agentId } = useParams<{ agentId: string }>()
  const { sessionId } = useAgentWizardStore()
  const [agentData, setAgentData] = useState<AgentConfig | null>(null)
  const [dismissed, setDismissed] = useState(false)

  const { messages, sendMessage, isConnected, isTyping, currentToolUse, resetChat } = useChatSocket({
    agentId: agentId ?? '',
    sessionId,
  })

  useEffect(() => {
    if (!agentId) return
    getAgent(agentId)
      .then(setAgentData)
      .catch(() => {
        // Use stored config as fallback
        const stored = useAgentWizardStore.getState().config
        setAgentData(stored as AgentConfig)
      })
  }, [agentId])

  const persona = agentData?.persona
  const agentName = persona?.name || 'Meu Agente'
  const agentAvatar = persona?.avatar_emoji || '🤖'

  const enabledSkills = agentData?.skills?.filter((s) => s.enabled) ?? []
  const memoryLabels: Record<string, string> = {
    none: 'Sem memória',
    buffer: 'Memória simples',
    semantic: 'Memória semântica',
    document: 'Memória com docs',
  }

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Banner CTA */}
      {!dismissed && (
        <div className="bg-gradient-to-r from-green-500 to-emerald-600 text-white px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">✅</span>
            <div>
              <p className="font-semibold text-sm">Você está testando seu agente!</p>
              <p className="text-xs text-green-100">Gostou? Baixe o pacote completo por R$ 9,99</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/wizard/${agentId}`}
              className="flex items-center gap-1.5 bg-white/20 hover:bg-white/30 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
            >
              <Download size={14} />
              Baixar
            </Link>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="text-green-200 hover:text-white text-lg leading-none"
              aria-label="Fechar"
            >
              ×
            </button>
          </div>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden max-h-[calc(100vh-60px)]">
        {/* Left sidebar */}
        <aside className="hidden md:flex flex-col w-72 bg-white border-r border-gray-100 shrink-0">
          <div className="p-5 border-b border-gray-100">
            <Link
              to={agentId ? `/wizard/${agentId}` : '/wizard'}
              className="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-800 font-medium mb-4"
            >
              <ArrowLeft size={16} />
              Voltar ao editor
            </Link>

            <div className="flex items-center gap-3 mb-3">
              <div className="w-14 h-14 bg-indigo-100 rounded-2xl flex items-center justify-center text-3xl">
                {agentAvatar}
              </div>
              <div>
                <h2 className="font-bold text-gray-900 text-lg">{agentName}</h2>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {isConnected ? (
                    <>
                      <Wifi size={12} className="text-green-500" />
                      <span className="text-xs text-green-600 font-medium">Online</span>
                    </>
                  ) : (
                    <>
                      <WifiOff size={12} className="text-red-400" />
                      <span className="text-xs text-red-500 font-medium">Reconectando...</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Config summary */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {agentData?.framework && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                  Framework
                </p>
                <div className="flex items-center gap-2 text-sm text-gray-700">
                  <span>{agentData.framework.icon}</span>
                  <span>{agentData.framework.name}</span>
                </div>
              </div>
            )}

            {agentData?.characteristics && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                  Tipo
                </p>
                <p className="text-sm text-gray-700">{agentData.characteristics.role_label}</p>
              </div>
            )}

            {agentData?.model && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                  Modelo
                </p>
                <p className="text-sm text-gray-700">
                  {agentData.model.model_name}
                  <span className="text-gray-400"> ({agentData.model.provider})</span>
                </p>
              </div>
            )}

            {agentData?.memory && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                  Memória
                </p>
                <p className="text-sm text-gray-700">
                  {memoryLabels[agentData.memory.type] ?? agentData.memory.type}
                </p>
              </div>
            )}

            {enabledSkills.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                  Habilidades
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {enabledSkills.map((s) => (
                    <span
                      key={s.id}
                      className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full"
                    >
                      {s.icon} {s.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {persona?.system_prompt && (
              <div>
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                  Instruções
                </p>
                <p className="text-xs text-gray-500 line-clamp-4 leading-relaxed">
                  {persona.system_prompt}
                </p>
              </div>
            )}
          </div>

          {/* Reset button */}
          <div className="p-4 border-t border-gray-100">
            <button
              type="button"
              onClick={resetChat}
              className="w-full flex items-center justify-center gap-2 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 px-4 py-2.5 rounded-xl hover:bg-gray-50 transition-colors font-medium"
            >
              <RotateCcw size={15} />
              Reiniciar conversa
            </button>
          </div>
        </aside>

        {/* Chat area */}
        <main className="flex-1 flex flex-col bg-gray-50 overflow-hidden">
          {/* Mobile header */}
          <div className="md:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-gray-100">
            <Link to={agentId ? `/wizard/${agentId}` : '/wizard'} className="text-indigo-600">
              <ArrowLeft size={20} />
            </Link>
            <div className="flex items-center gap-2">
              <span className="text-xl">{agentAvatar}</span>
              <span className="font-semibold text-gray-900">{agentName}</span>
              {isConnected ? (
                <Wifi size={14} className="text-green-500" />
              ) : (
                <WifiOff size={14} className="text-red-400" />
              )}
            </div>
            <button type="button" onClick={resetChat}>
              <RotateCcw size={18} className="text-gray-400" />
            </button>
          </div>

          {/* Messages */}
          <ChatWindow
            messages={messages}
            isTyping={isTyping}
            currentToolUse={currentToolUse}
            agentAvatar={agentAvatar}
            agentName={agentName}
          />

          {/* Input */}
          <ChatInput onSend={sendMessage} disabled={isTyping || !isConnected} />
        </main>
      </div>
    </div>
  )
}
