import { useState, useRef, useCallback, useEffect } from 'react'

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  content: string
  timestamp: Date
  isStreaming?: boolean
  toolUse?: string
}

interface UseChatSocketOptions {
  agentId: string
  sessionId: string
}

interface UseChatSocketReturn {
  messages: ChatMessage[]
  sendMessage: (text: string) => void
  isConnected: boolean
  isTyping: boolean
  currentToolUse: string | null
  resetChat: () => void
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 11)
}

export function useChatSocket({ agentId, sessionId }: UseChatSocketOptions): UseChatSocketReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [currentToolUse, setCurrentToolUse] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const currentMsgIdRef = useRef<string | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/chat/${agentId}?session_id=${sessionId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
    }

    ws.onclose = () => {
      setIsConnected(false)
      setIsTyping(false)
      setCurrentToolUse(null)
      // Attempt to reconnect after 3 seconds
      setTimeout(() => {
        if (wsRef.current === ws) {
          connect()
        }
      }, 3000)
    }

    ws.onerror = () => {
      setIsConnected(false)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case 'token': {
            // Streaming token - append to current message
            const token: string = data.token
            setMessages((prev) => {
              const msgId = currentMsgIdRef.current
              if (!msgId) return prev
              return prev.map((m) =>
                m.id === msgId ? { ...m, content: m.content + token, isStreaming: true } : m
              )
            })
            break
          }

          case 'message_start': {
            // New agent message starting
            setIsTyping(true)
            const newId = generateId()
            currentMsgIdRef.current = newId
            setMessages((prev) => [
              ...prev,
              {
                id: newId,
                role: 'agent',
                content: '',
                timestamp: new Date(),
                isStreaming: true,
              },
            ])
            break
          }

          case 'message_end': {
            // Agent message complete
            setIsTyping(false)
            setCurrentToolUse(null)
            currentMsgIdRef.current = null
            setMessages((prev) =>
              prev.map((m) =>
                m.isStreaming ? { ...m, isStreaming: false } : m
              )
            )
            break
          }

          case 'tool_use': {
            setCurrentToolUse(data.tool_name)
            break
          }

          case 'tool_result': {
            setCurrentToolUse(null)
            break
          }

          case 'error': {
            setIsTyping(false)
            setCurrentToolUse(null)
            currentMsgIdRef.current = null
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: 'agent',
                content: '❌ Ocorreu um erro. Por favor, tente novamente.',
                timestamp: new Date(),
              },
            ])
            break
          }

          default:
            break
        }
      } catch {
        // Non-JSON message, ignore
      }
    }
  }, [agentId, sessionId])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  const sendMessage = useCallback((text: string) => {
    if (!text.trim()) return
    if (wsRef.current?.readyState !== WebSocket.OPEN) return

    const userMsg: ChatMessage = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMsg])
    setIsTyping(true)

    wsRef.current.send(JSON.stringify({ type: 'message', content: text.trim() }))
  }, [])

  const resetChat = useCallback(() => {
    setMessages([])
    setIsTyping(false)
    setCurrentToolUse(null)
    currentMsgIdRef.current = null
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'reset' }))
    }
  }, [])

  return { messages, sendMessage, isConnected, isTyping, currentToolUse, resetChat }
}
