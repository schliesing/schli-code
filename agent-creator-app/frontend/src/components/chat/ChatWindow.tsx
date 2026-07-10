import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../../hooks/useChatSocket'

interface ChatWindowProps {
  messages: ChatMessage[]
  isTyping: boolean
  currentToolUse: string | null
  agentAvatar: string
  agentName: string
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-1 px-4 py-3 bg-white border border-gray-100 rounded-2xl rounded-tl-sm shadow-sm">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-2 h-2 bg-gray-400 rounded-full typing-dot"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
    </div>
  )
}

function renderMarkdown(text: string): string {
  return text
    // Code blocks
    .replace(/```(\w+)?\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Bold
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Unordered list items
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    // Ordered list items
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Wrap consecutive li items
    .replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`)
    // Line breaks (not inside pre)
    .replace(/\n(?!<\/?(ul|li|pre|code))/g, '<br />')
}

const TOOL_USE_LABELS: Record<string, string> = {
  web_search: '🔍 Pesquisando na web...',
  file_reader: '📄 Lendo arquivo...',
  code_executor: '⚡ Executando código...',
  email: '📧 Enviando e-mail...',
  calendar: '📅 Acessando calendário...',
  image_gen: '🎨 Gerando imagem...',
  weather: '🌤️ Verificando clima...',
  calculator: '🧮 Calculando...',
  translate: '🌐 Traduzindo...',
}

export function ChatWindow({ messages, isTyping, currentToolUse, agentAvatar, agentName }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
        <div className="w-20 h-20 bg-indigo-100 rounded-full flex items-center justify-center text-4xl mb-4">
          {agentAvatar}
        </div>
        <h3 className="font-bold text-gray-900 text-xl mb-2">{agentName}</h3>
        <p className="text-gray-500 text-sm max-w-xs">
          Envie uma mensagem para iniciar a conversa com seu agente!
        </p>
        <div className="mt-6 flex flex-col gap-2 w-full max-w-xs">
          <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">
            Sugestões para testar:
          </p>
          {['Olá! Quem é você?', 'O que você pode fazer?', 'Me ajuda com uma tarefa?'].map((s) => (
            <div
              key={s}
              className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-2 text-sm text-gray-600"
            >
              {s}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex items-end gap-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          {/* Agent avatar */}
          {message.role === 'agent' && (
            <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-lg shrink-0 mb-0.5">
              {agentAvatar}
            </div>
          )}

          <div className={`max-w-[80%] ${message.role === 'user' ? 'items-end' : 'items-start'} flex flex-col`}>
            {/* Message bubble */}
            <div
              className={`px-4 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${
                message.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-sm'
                  : 'bg-white border border-gray-100 text-gray-800 rounded-bl-sm'
              }`}
            >
              {message.role === 'agent' ? (
                <div
                  className="chat-markdown"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(message.content) }}
                />
              ) : (
                <p>{message.content}</p>
              )}
              {message.isStreaming && (
                <span className="inline-block w-1 h-4 bg-indigo-400 ml-0.5 animate-pulse rounded-sm" />
              )}
            </div>

            {/* Timestamp */}
            <span className="text-xs text-gray-400 mt-1 px-1">
              {message.timestamp.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
        </div>
      ))}

      {/* Tool use indicator */}
      {currentToolUse && (
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-lg shrink-0">
            {agentAvatar}
          </div>
          <div className="bg-indigo-50 border border-indigo-200 text-indigo-700 text-sm px-4 py-2 rounded-xl flex items-center gap-2">
            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-ping" />
            {TOOL_USE_LABELS[currentToolUse] ?? `🔧 Usando ferramenta: ${currentToolUse}...`}
          </div>
        </div>
      )}

      {/* Typing indicator */}
      {isTyping && !currentToolUse && messages[messages.length - 1]?.role !== 'agent' && (
        <div className="flex items-end gap-2">
          <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-lg shrink-0">
            {agentAvatar}
          </div>
          <TypingIndicator />
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
