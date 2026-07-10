import { useState } from 'react'
import { ChevronDown, ChevronUp, Eye, EyeOff } from 'lucide-react'
import { TooltipInfo } from '../ui/TooltipInfo'
import { useAgentWizardStore } from '../../store/agentWizardStore'
import type { DeploymentTarget } from '../../types/agent'
import { clsx } from 'clsx'

interface DeploymentOption {
  type: DeploymentTarget['type']
  icon: string
  name: string
  difficulty: string
  difficultyColor: string
  description: string
  beginner_explanation: string
  configFields: {
    key: string
    label: string
    type: string
    placeholder: string
    helpText?: string
    helpUrl?: string
  }[]
  setupSteps: string[]
}

const DEPLOYMENT_OPTIONS: DeploymentOption[] = [
  {
    type: 'telegram',
    icon: '📱',
    name: 'Telegram',
    difficulty: '⭐ Mais fácil — 5 minutos',
    difficultyColor: 'text-green-600',
    description: 'Seu agente no Telegram, pronto para conversar',
    beginner_explanation:
      'O Telegram é o jeito mais fácil de colocar seu agente no ar. Em apenas 5 minutos você terá um bot no Telegram pronto para conversar com qualquer pessoa.',
    configFields: [
      {
        key: 'bot_token',
        label: 'Token do Bot Telegram',
        type: 'password',
        placeholder: '123456789:ABCDEFGhijklmnop...',
        helpText: 'Obter token no BotFather',
        helpUrl: 'https://t.me/BotFather',
      },
    ],
    setupSteps: [
      'Abra o Telegram e pesquise por @BotFather',
      'Envie o comando /newbot',
      'Escolha um nome e username para seu bot',
      'Copie o token gerado e cole aqui',
      'Pronto! Seu bot estará online após o deploy',
    ],
  },
  {
    type: 'discord',
    icon: '🎮',
    name: 'Discord',
    difficulty: 'Médio — 10 minutos',
    difficultyColor: 'text-yellow-600',
    description: 'Bot no Discord para o seu servidor',
    beginner_explanation:
      'Coloque seu agente em um servidor do Discord. Ideal para comunidades e jogadores. Requer criar um aplicativo no Discord Developer Portal.',
    configFields: [
      {
        key: 'bot_token',
        label: 'Token do Bot Discord',
        type: 'password',
        placeholder: 'MTIz...seu token aqui...',
        helpText: 'Criar aplicativo no Discord',
        helpUrl: 'https://discord.com/developers/applications',
      },
      {
        key: 'guild_id',
        label: 'ID do Servidor (opcional)',
        type: 'text',
        placeholder: '1234567890',
      },
    ],
    setupSteps: [
      'Acesse discord.com/developers/applications',
      'Clique em "New Application" e dê um nome',
      'Vá em "Bot" e clique em "Add Bot"',
      'Copie o token e cole aqui',
      'Em "OAuth2 > URL Generator", selecione "bot" e as permissões desejadas',
      'Use a URL gerada para adicionar o bot ao seu servidor',
    ],
  },
  {
    type: 'widget',
    icon: '🖥️',
    name: 'Widget para Site',
    difficulty: 'Fácil — copie e cole',
    difficultyColor: 'text-green-600',
    description: 'Janelinha de chat no seu site ou landing page',
    beginner_explanation:
      'Um widget é uma janelinha de chat que aparece no canto do seu site. Você recebe um código para colar no seu site e pronto! Funciona em qualquer site HTML.',
    configFields: [
      {
        key: 'primary_color',
        label: 'Cor principal do widget',
        type: 'color',
        placeholder: '#4F46E5',
      },
      {
        key: 'position',
        label: 'Posição na tela',
        type: 'select',
        placeholder: 'bottom-right',
      },
    ],
    setupSteps: [
      'Escolha a cor do widget aqui',
      'Após o deploy, você receberá um código JavaScript',
      'Cole o código antes do </body> no seu site',
      'O chat aparecerá automaticamente no canto da tela',
    ],
  },
  {
    type: 'api',
    icon: '🌐',
    name: 'API REST',
    difficulty: 'Para desenvolvedores',
    difficultyColor: 'text-blue-600',
    description: 'Endpoint HTTP para integrar em qualquer sistema',
    beginner_explanation:
      'A API REST é para desenvolvedores que querem integrar o agente em seus próprios sistemas, apps ou sites. Você receberá uma URL e poderá enviar mensagens via código.',
    configFields: [
      {
        key: 'port',
        label: 'Porta do servidor',
        type: 'number',
        placeholder: '8080',
      },
      {
        key: 'api_key',
        label: 'Chave de autenticação (opcional)',
        type: 'password',
        placeholder: 'Deixe em branco para sem autenticação',
      },
    ],
    setupSteps: [
      'Configure a porta e chave de API',
      'Após o deploy, sua API estará em http://localhost:PORTA',
      'Endpoint: POST /chat com body: {"message": "Olá"}',
      'A resposta será: {"response": "...", "session_id": "..."}',
    ],
  },
  {
    type: 'whatsapp',
    icon: '💬',
    name: 'WhatsApp',
    difficulty: 'Avançado — requer Twilio',
    difficultyColor: 'text-red-600',
    description: 'Integre com WhatsApp via Twilio',
    beginner_explanation:
      'Coloque seu agente no WhatsApp! Isso requer uma conta no Twilio (serviço de comunicação) e pode ter custos. É a opção mais completa mas também a mais complexa.',
    configFields: [
      {
        key: 'twilio_account_sid',
        label: 'Twilio Account SID',
        type: 'text',
        placeholder: 'ACxxxxxxxxxxxxxxxx',
        helpText: 'Criar conta no Twilio',
        helpUrl: 'https://www.twilio.com',
      },
      {
        key: 'twilio_auth_token',
        label: 'Twilio Auth Token',
        type: 'password',
        placeholder: 'seu auth token aqui',
      },
      {
        key: 'twilio_number',
        label: 'Número WhatsApp Twilio',
        type: 'text',
        placeholder: '+14155238886',
      },
    ],
    setupSteps: [
      'Crie uma conta no Twilio (twilio.com)',
      'Ative o Twilio Sandbox for WhatsApp',
      'Copie o Account SID e Auth Token',
      'Configure o número do WhatsApp Twilio',
      'Após o deploy, configure o webhook no Twilio',
    ],
  },
]

export function StepDeployment() {
  const { config, updateConfig } = useAgentWizardStore()
  const [expandedGuide, setExpandedGuide] = useState<string | null>(null)
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({})
  const [selectedColor, setSelectedColor] = useState('#4F46E5')

  const targets: DeploymentTarget[] = config.deployment?.targets ?? DEPLOYMENT_OPTIONS.map((o) => ({
    type: o.type,
    enabled: false,
    config: {},
  }))

  function toggleTarget(type: DeploymentTarget['type']) {
    const updated = targets.map((t) =>
      t.type === type ? { ...t, enabled: !t.enabled } : t
    )
    updateConfig({ deployment: { targets: updated } })
  }

  function updateTargetConfig(type: DeploymentTarget['type'], key: string, value: string) {
    const updated = targets.map((t) =>
      t.type === type ? { ...t, config: { ...t.config, [key]: value } } : t
    )
    updateConfig({ deployment: { targets: updated } })
  }

  function getTargetConfig(type: DeploymentTarget['type']) {
    return targets.find((t) => t.type === type)?.config ?? {}
  }

  function isEnabled(type: DeploymentTarget['type']) {
    return targets.find((t) => t.type === type)?.enabled ?? false
  }

  const enabledCount = targets.filter((t) => t.enabled).length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-gray-600 text-base">
          Onde você quer que as pessoas falem com seu agente? Você pode ativar mais de uma opção!
        </p>
        {enabledCount > 0 && (
          <span className="bg-indigo-100 text-indigo-700 text-sm font-semibold px-3 py-1 rounded-full">
            {enabledCount} destino{enabledCount !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      <div className="space-y-3">
        {DEPLOYMENT_OPTIONS.map((option) => {
          const enabled = isEnabled(option.type)
          const targetConfig = getTargetConfig(option.type)

          return (
            <div
              key={option.type}
              className={clsx(
                'border-2 rounded-xl transition-all duration-200 overflow-hidden',
                enabled ? 'border-indigo-300' : 'border-gray-100'
              )}
            >
              {/* Card header */}
              <div className="flex items-center gap-4 p-4 bg-white">
                <span className="text-3xl">{option.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-bold text-gray-900">{option.name}</h3>
                    <TooltipInfo text={option.beginner_explanation} />
                    <span className={`text-xs font-semibold ${option.difficultyColor}`}>
                      {option.difficulty}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-0.5">{option.description}</p>
                </div>

                {/* Toggle */}
                <button
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  onClick={() => toggleTarget(option.type)}
                  className={clsx(
                    'relative w-12 h-6 rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-indigo-400 shrink-0',
                    enabled ? 'bg-indigo-600' : 'bg-gray-300'
                  )}
                >
                  <span
                    className={clsx(
                      'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-300',
                      enabled ? 'translate-x-6' : 'translate-x-0'
                    )}
                  />
                </button>
              </div>

              {/* Config fields when enabled */}
              {enabled && (
                <div className="bg-indigo-50 px-5 py-4 space-y-3 border-t border-indigo-100 animate-fade-in">
                  {option.configFields.map((field) => (
                    <div key={field.key}>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {field.label}
                        {field.helpText && field.helpUrl && (
                          <a
                            href={field.helpUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-2 text-xs text-indigo-600 hover:underline"
                          >
                            {field.helpText} ↗
                          </a>
                        )}
                      </label>

                      {field.type === 'color' ? (
                        <div className="flex items-center gap-3">
                          <input
                            type="color"
                            value={targetConfig[field.key] ?? selectedColor}
                            onChange={(e) => {
                              setSelectedColor(e.target.value)
                              updateTargetConfig(option.type, field.key, e.target.value)
                            }}
                            className="w-12 h-10 rounded-lg border border-gray-200 cursor-pointer"
                          />
                          <span className="text-sm text-gray-600 font-mono">
                            {targetConfig[field.key] ?? selectedColor}
                          </span>
                        </div>
                      ) : field.type === 'select' ? (
                        <select
                          className="input-field"
                          value={targetConfig[field.key] ?? 'bottom-right'}
                          onChange={(e) => updateTargetConfig(option.type, field.key, e.target.value)}
                        >
                          <option value="bottom-right">Canto inferior direito</option>
                          <option value="bottom-left">Canto inferior esquerdo</option>
                        </select>
                      ) : (
                        <div className="relative">
                          <input
                            type={
                              field.type === 'password' && !showPasswords[`${option.type}-${field.key}`]
                                ? 'password'
                                : 'text'
                            }
                            className="input-field pr-10"
                            placeholder={field.placeholder}
                            value={targetConfig[field.key] ?? ''}
                            onChange={(e) => updateTargetConfig(option.type, field.key, e.target.value)}
                          />
                          {field.type === 'password' && (
                            <button
                              type="button"
                              onClick={() =>
                                setShowPasswords((prev) => ({
                                  ...prev,
                                  [`${option.type}-${field.key}`]:
                                    !prev[`${option.type}-${field.key}`],
                                }))
                              }
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                            >
                              {showPasswords[`${option.type}-${field.key}`] ? (
                                <EyeOff size={16} />
                              ) : (
                                <Eye size={16} />
                              )}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Setup guide */}
                  <div className="border border-indigo-200 rounded-lg overflow-hidden">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedGuide(expandedGuide === option.type ? null : option.type)
                      }
                      className="w-full flex items-center justify-between px-4 py-2.5 bg-white text-sm font-medium text-indigo-700 hover:bg-indigo-50"
                    >
                      <span>📋 Guia de configuração passo a passo</span>
                      {expandedGuide === option.type ? (
                        <ChevronUp size={16} />
                      ) : (
                        <ChevronDown size={16} />
                      )}
                    </button>
                    {expandedGuide === option.type && (
                      <div className="px-4 py-3 bg-white border-t border-indigo-100">
                        <ol className="list-decimal list-inside space-y-1.5 text-sm text-gray-700">
                          {option.setupSteps.map((step, idx) => (
                            <li key={idx}>{step}</li>
                          ))}
                        </ol>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {enabledCount === 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-amber-700 text-sm">
          💡 <strong>Dica:</strong> Você pode configurar o deploy depois. Por enquanto, ative pelo
          menos um destino ou prossiga para revisar seu agente.
        </div>
      )}
    </div>
  )
}
