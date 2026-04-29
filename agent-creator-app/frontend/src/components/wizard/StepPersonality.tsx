import { useState } from 'react'
import { TooltipInfo } from '../ui/TooltipInfo'
import { useAgentWizardStore } from '../../store/agentWizardStore'
import type { PersonaConfig } from '../../types/agent'
import { clsx } from 'clsx'

const AVATAR_EMOJIS = [
  '🤖', '🧑‍💼', '👩‍💼', '🧑‍🔬', '👩‍🏫', '🧑‍💻', '👩‍💻', '🦸', '🧙',
  '🤓', '😊', '🦊', '🐻', '🦁', '🐧', '🦅', '🌟', '💡', '🎯', '🚀',
  '🌈', '💎', '🔮', '🧠',
]

const TONE_OPTIONS = [
  {
    id: 'professional' as const,
    label: 'Profissional',
    icon: '👔',
    description: 'Formal e objetivo, ideal para ambientes corporativos',
  },
  {
    id: 'friendly' as const,
    label: 'Amigável',
    icon: '😊',
    description: 'Caloroso e acessível — recomendado para a maioria',
    recommended: true,
  },
  {
    id: 'casual' as const,
    label: 'Descontraído',
    icon: '😎',
    description: 'Informal e divertido, ótimo para jovens e entretenimento',
  },
  {
    id: 'direct' as const,
    label: 'Direto ao ponto',
    icon: '⚡',
    description: 'Respostas curtas e objetivas, sem rodeios',
  },
]

const LANGUAGE_OPTIONS = [
  { id: 'pt-BR' as const, flag: '🇧🇷', label: 'Português (Brasil)' },
  { id: 'en-US' as const, flag: '🇺🇸', label: 'English (US)' },
  { id: 'es-ES' as const, flag: '🇪🇸', label: 'Español' },
]

const SYSTEM_PROMPT_PRESETS = [
  {
    label: '🙋 Assistente geral',
    prompt:
      'Você é um assistente prestativo, claro e amigável. Responda sempre em português do Brasil. Seja conciso mas completo. Se não souber a resposta, diga honestamente.',
  },
  {
    label: '💁 Atendimento ao cliente',
    prompt:
      'Você é um agente de atendimento ao cliente educado e empático. Sempre cumprimente o cliente, entenda seu problema com clareza e ofereça soluções práticas. Se não puder resolver, encaminhe para um humano de forma gentil.',
  },
  {
    label: '👨‍💻 Assistente de código',
    prompt:
      'Você é um especialista em programação. Explique conceitos de forma clara, escreva código limpo e bem comentado, e sempre sugira boas práticas. Quando houver erros, explique o que causou o problema e como corrigir.',
  },
  {
    label: '🔬 Pesquisador',
    prompt:
      'Você é um pesquisador rigoroso e detalhista. Busque informações precisas, cite fontes quando possível, apresente múltiplas perspectivas e sempre indique o nível de certeza das informações.',
  },
  {
    label: '📚 Professor',
    prompt:
      'Você é um professor paciente e didático. Adapte suas explicações ao nível do aluno, use exemplos práticos do cotidiano, faça perguntas para verificar o entendimento e encoraje a curiosidade.',
  },
  {
    label: '💼 Consultor de negócios',
    prompt:
      'Você é um consultor de negócios experiente. Analise situações de forma estratégica, apresente prós e contras, sugira soluções baseadas em dados e boas práticas do mercado.',
  },
]

const DEFAULT_PERSONA: PersonaConfig = {
  name: '',
  avatar_emoji: '🤖',
  greeting: '',
  tone: 'friendly',
  system_prompt: '',
  language: 'pt-BR',
}

export function StepPersonality() {
  const { config, updateConfig } = useAgentWizardStore()
  const persona: PersonaConfig = config.persona ?? DEFAULT_PERSONA
  const [charCount, setCharCount] = useState(persona.system_prompt.length)

  function updatePersona(patch: Partial<PersonaConfig>) {
    updateConfig({ persona: { ...persona, ...patch } })
  }

  function handleSystemPromptChange(value: string) {
    setCharCount(value.length)
    updatePersona({ system_prompt: value })
  }

  function loadPreset(prompt: string) {
    setCharCount(prompt.length)
    updatePersona({ system_prompt: prompt })
  }

  return (
    <div className="space-y-6">
      <p className="text-gray-600 text-base">
        Dê uma identidade ao seu agente! Quanto mais personalidade ele tiver, mais natural e
        envolvente serão as conversas.
      </p>

      {/* Name + Avatar row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Name */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Nome do agente
            <TooltipInfo text="O nome que seu agente usará para se apresentar. Pode ser um nome de pessoa ou um nome criativo!" />
          </label>
          <input
            type="text"
            className="input-field text-lg"
            placeholder="Ex: Sofia, Max, AtendBot..."
            maxLength={30}
            value={persona.name}
            onChange={(e) => updatePersona({ name: e.target.value })}
          />
        </div>

        {/* Language */}
        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Idioma principal
          </label>
          <div className="flex gap-2">
            {LANGUAGE_OPTIONS.map((lang) => (
              <button
                key={lang.id}
                type="button"
                onClick={() => updatePersona({ language: lang.id })}
                className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl border-2 text-sm font-medium transition-all ${
                  persona.language === lang.id
                    ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                    : 'border-gray-200 text-gray-600 hover:border-indigo-300'
                }`}
              >
                <span>{lang.flag}</span>
                <span className="hidden sm:inline">{lang.label.split(' ')[0]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Avatar picker */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          Avatar do agente
          <TooltipInfo text="Escolha um emoji que represente a personalidade do seu agente. Este emoji aparecerá no chat." />
        </label>
        <div className="flex flex-wrap gap-2 p-4 bg-gray-50 rounded-xl">
          {AVATAR_EMOJIS.map((emoji) => (
            <button
              key={emoji}
              type="button"
              onClick={() => updatePersona({ avatar_emoji: emoji })}
              className={clsx(
                'w-10 h-10 text-2xl rounded-xl flex items-center justify-center transition-all hover:scale-110',
                persona.avatar_emoji === emoji
                  ? 'bg-indigo-100 ring-2 ring-indigo-500 scale-110'
                  : 'hover:bg-gray-200'
              )}
            >
              {emoji}
            </button>
          ))}
        </div>
        {persona.avatar_emoji && (
          <p className="mt-2 text-sm text-gray-500">
            Selecionado: <span className="text-2xl">{persona.avatar_emoji}</span>
          </p>
        )}
      </div>

      {/* Greeting */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-2">
          Mensagem de boas-vindas
          <TooltipInfo text="Esta é a primeira mensagem que seu agente envia quando alguém inicia uma conversa. Faça ela convidativa!" />
        </label>
        <textarea
          className="input-field"
          rows={2}
          placeholder={`Ex: Olá! Sou ${persona.name || 'seu assistente'}, como posso te ajudar hoje? 😊`}
          value={persona.greeting}
          onChange={(e) => updatePersona({ greeting: e.target.value })}
        />
      </div>

      {/* Tone selector */}
      <div>
        <label className="block text-sm font-semibold text-gray-700 mb-3">
          Tom de voz
          <TooltipInfo text="O tom de voz define como seu agente se comunica. Escolha o que combina mais com sua marca ou objetivo." />
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {TONE_OPTIONS.map((tone) => (
            <button
              key={tone.id}
              type="button"
              onClick={() => updatePersona({ tone: tone.id })}
              className={clsx(
                'relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 text-center transition-all hover:shadow-md',
                persona.tone === tone.id
                  ? 'border-indigo-500 bg-indigo-50'
                  : 'border-gray-200 hover:border-indigo-300'
              )}
            >
              {tone.recommended && (
                <span className="absolute -top-2 left-1/2 -translate-x-1/2 badge-beginner text-xs px-2">
                  ⭐ Recomendado
                </span>
              )}
              <span className="text-2xl">{tone.icon}</span>
              <span className="font-semibold text-gray-900 text-sm">{tone.label}</span>
              <span className="text-xs text-gray-500">{tone.description}</span>
            </button>
          ))}
        </div>
      </div>

      {/* System prompt */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-semibold text-gray-700">
            Instruções do agente (Prompt)
            <TooltipInfo text="As instruções definem como seu agente se comporta, o que ele sabe e como responde. Quanto mais detalhado, melhor! Use um modelo abaixo para começar." />
          </label>
          <span className="text-xs text-gray-400">{charCount} caracteres</span>
        </div>

        {/* Preset buttons */}
        <div className="flex flex-wrap gap-2 mb-3">
          {SYSTEM_PROMPT_PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => loadPreset(preset.prompt)}
              className="text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 px-3 py-1.5 rounded-lg font-medium transition-colors"
            >
              {preset.label}
            </button>
          ))}
        </div>

        <textarea
          className="input-field font-mono text-sm"
          rows={6}
          placeholder="Descreva como seu agente deve se comportar, o que ele sabe, como deve responder, tom de voz, limitações, etc..."
          value={persona.system_prompt}
          onChange={(e) => handleSystemPromptChange(e.target.value)}
        />
        <p className="text-xs text-gray-400 mt-1">
          💡 Clique em um modelo acima para começar e depois personalize à vontade
        </p>
      </div>

      {/* Preview */}
      {(persona.name || persona.greeting) && (
        <div className="bg-gray-50 rounded-xl p-4 border border-gray-200 animate-fade-in">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Pré-visualização
          </p>
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center text-xl shrink-0">
              {persona.avatar_emoji}
            </div>
            <div>
              <p className="font-semibold text-gray-900 text-sm">{persona.name || 'Meu Agente'}</p>
              <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-2 mt-1 max-w-sm">
                <p className="text-sm text-gray-700">
                  {persona.greeting ||
                    `Olá! Sou ${persona.name || 'seu assistente'}, como posso te ajudar? 😊`}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
