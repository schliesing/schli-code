import { useState } from 'react'
import { Eye, EyeOff, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { StepCard } from '../ui/StepCard'
import { TooltipInfo } from '../ui/TooltipInfo'
import { useAgentWizardStore } from '../../store/agentWizardStore'
import type { ModelConfig } from '../../types/agent'

interface CloudModel {
  provider: string
  providerIcon: string
  models: {
    id: string
    name: string
    description: string
    recommended: boolean
    apiKeyLink: string
    apiKeyLabel: string
    placeholder: string
  }[]
}

const CLOUD_PROVIDERS: CloudModel[] = [
  {
    provider: 'OpenAI',
    providerIcon: '🟢',
    models: [
      {
        id: 'gpt-4o-mini',
        name: 'GPT-4o Mini',
        description: 'Rápido e econômico — perfeito para começar',
        recommended: true,
        apiKeyLink: 'https://platform.openai.com/api-keys',
        apiKeyLabel: 'Chave da API OpenAI',
        placeholder: 'sk-...',
      },
      {
        id: 'gpt-4o',
        name: 'GPT-4o',
        description: 'Mais poderoso, ideal para tarefas complexas',
        recommended: false,
        apiKeyLink: 'https://platform.openai.com/api-keys',
        apiKeyLabel: 'Chave da API OpenAI',
        placeholder: 'sk-...',
      },
    ],
  },
  {
    provider: 'Anthropic',
    providerIcon: '🔵',
    models: [
      {
        id: 'claude-3-haiku-20240307',
        name: 'Claude Haiku',
        description: 'Rápido, inteligente e econômico',
        recommended: false,
        apiKeyLink: 'https://console.anthropic.com/settings/keys',
        apiKeyLabel: 'Chave da API Anthropic',
        placeholder: 'sk-ant-...',
      },
      {
        id: 'claude-3-5-sonnet-20241022',
        name: 'Claude Sonnet 3.5',
        description: 'Excelente equilíbrio entre qualidade e custo',
        recommended: false,
        apiKeyLink: 'https://console.anthropic.com/settings/keys',
        apiKeyLabel: 'Chave da API Anthropic',
        placeholder: 'sk-ant-...',
      },
    ],
  },
  {
    provider: 'Google',
    providerIcon: '🔴',
    models: [
      {
        id: 'gemini-1.5-flash',
        name: 'Gemini 1.5 Flash',
        description: 'Muito rápido e com contexto enorme',
        recommended: false,
        apiKeyLink: 'https://aistudio.google.com/app/apikey',
        apiKeyLabel: 'Chave da API Google AI',
        placeholder: 'AIza...',
      },
      {
        id: 'gemini-1.5-pro',
        name: 'Gemini 1.5 Pro',
        description: 'Modelo avançado do Google com 1 milhão de tokens de contexto',
        recommended: false,
        apiKeyLink: 'https://aistudio.google.com/app/apikey',
        apiKeyLabel: 'Chave da API Google AI',
        placeholder: 'AIza...',
      },
    ],
  },
]

const LOCAL_MODELS = [
  { id: 'llama3.2:3b', name: 'Llama 3.2 (3B)', size: '2.0 GB', speed: '⭐⭐⭐', description: 'Leve e rápido', recommended: true },
  { id: 'llama3.1:8b', name: 'Llama 3.1 (8B)', size: '4.7 GB', speed: '⭐⭐', description: 'Bom equilíbrio', recommended: false },
  { id: 'mistral:7b', name: 'Mistral 7B', size: '4.1 GB', speed: '⭐⭐', description: 'Ótimo para português', recommended: false },
  { id: 'phi3:mini', name: 'Phi-3 Mini', size: '2.3 GB', speed: '⭐⭐⭐', description: 'Compacto e eficiente', recommended: false },
  { id: 'gemma2:9b', name: 'Gemma 2 (9B)', size: '5.4 GB', speed: '⭐⭐', description: 'Do Google, código aberto', recommended: false },
]

export function StepModel() {
  const { config, updateConfig } = useAgentWizardStore()
  const [activeTab, setActiveTab] = useState<'cloud' | 'local'>('cloud')
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({})
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [showOllamaGuide, setShowOllamaGuide] = useState(false)
  const [localUrl, setLocalUrl] = useState('http://localhost:11434')

  const selectedModelId = config.model?.model_id

  function handleCloudSelect(provider: CloudModel, model: (typeof provider.models)[0]) {
    const mc: ModelConfig = {
      provider: provider.provider,
      model_id: model.id,
      model_name: model.name,
      api_key: apiKeys[model.id] ?? '',
      local: false,
      recommended: model.recommended,
    }
    updateConfig({ model: mc })
  }

  function handleLocalSelect(model: (typeof LOCAL_MODELS)[0]) {
    const mc: ModelConfig = {
      provider: 'Ollama',
      model_id: model.id,
      model_name: model.name,
      local: true,
      local_url: localUrl,
      recommended: model.recommended,
    }
    updateConfig({ model: mc })
  }

  function handleApiKeyChange(modelId: string, value: string) {
    const updated = { ...apiKeys, [modelId]: value }
    setApiKeys(updated)
    if (config.model?.model_id === modelId) {
      updateConfig({ model: { ...config.model, api_key: value } })
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-gray-600 text-base">
        O modelo de IA é o "cérebro" do seu agente. Você pode usar serviços na nuvem ou rodar
        localmente no seu computador.
      </p>

      {/* Tabs */}
      <div className="flex gap-2 bg-gray-100 p-1 rounded-xl w-fit">
        <button
          type="button"
          onClick={() => setActiveTab('cloud')}
          className={`px-5 py-2.5 rounded-lg font-semibold text-sm transition-all ${
            activeTab === 'cloud'
              ? 'bg-white text-indigo-600 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          Na Nuvem ☁️
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('local')}
          className={`px-5 py-2.5 rounded-lg font-semibold text-sm transition-all ${
            activeTab === 'local'
              ? 'bg-white text-indigo-600 shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
          }`}
        >
          No seu Computador 💻
        </button>
      </div>

      {/* Cloud models */}
      {activeTab === 'cloud' && (
        <div className="space-y-6 animate-fade-in">
          {CLOUD_PROVIDERS.map((provider) => (
            <div key={provider.provider}>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">{provider.providerIcon}</span>
                <h3 className="font-semibold text-gray-800">{provider.provider}</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {provider.models.map((model) => (
                  <div key={model.id} className="space-y-2">
                    <StepCard
                      selected={selectedModelId === model.id}
                      onClick={() => handleCloudSelect(provider, model)}
                      badge={model.recommended ? '⭐ Recomendado' : undefined}
                    >
                      <div className="pt-1">
                        <h4 className="font-semibold text-gray-900">{model.name}</h4>
                        <p className="text-sm text-gray-500 mt-0.5">{model.description}</p>
                      </div>
                    </StepCard>

                    {selectedModelId === model.id && (
                      <div className="animate-fade-in bg-gray-50 rounded-xl p-4 space-y-2">
                        <label className="block text-sm font-medium text-gray-700">
                          {model.apiKeyLabel}
                          <TooltipInfo text="Uma chave de API é como uma senha que permite ao seu agente usar o serviço de IA. Você precisa criar uma conta no site do provedor para obter essa chave." />
                        </label>
                        <div className="relative">
                          <input
                            type={showKeys[model.id] ? 'text' : 'password'}
                            className="input-field pr-10"
                            placeholder={model.placeholder}
                            value={apiKeys[model.id] ?? ''}
                            onChange={(e) => handleApiKeyChange(model.id, e.target.value)}
                          />
                          <button
                            type="button"
                            onClick={() =>
                              setShowKeys((prev) => ({ ...prev, [model.id]: !prev[model.id] }))
                            }
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                          >
                            {showKeys[model.id] ? <EyeOff size={16} /> : <Eye size={16} />}
                          </button>
                        </div>
                        <a
                          href={model.apiKeyLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-indigo-600 hover:underline"
                        >
                          Criar minha chave gratuita <ExternalLink size={12} />
                        </a>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Local models */}
      {activeTab === 'local' && (
        <div className="space-y-4 animate-fade-in">
          <div className="bg-green-50 border border-green-200 rounded-xl p-4">
            <p className="text-green-800 font-medium text-sm">
              💡 Modelos locais rodam no seu computador, sem custo por uso! Nenhuma informação sai
              do seu dispositivo.
            </p>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
            <p className="text-amber-800 text-sm">
              ⚠️ <strong>Requisito:</strong> Requer pelo menos 8GB de RAM e o Ollama instalado.
            </p>
          </div>

          {/* Ollama setup guide */}
          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowOllamaGuide(!showOllamaGuide)}
              className="w-full flex items-center justify-between px-5 py-4 text-gray-700 hover:bg-gray-50 font-medium"
            >
              <span>📖 Como instalar o Ollama</span>
              {showOllamaGuide ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            {showOllamaGuide && (
              <div className="px-5 pb-5 border-t border-gray-100 pt-4 space-y-3">
                <ol className="list-decimal list-inside space-y-2 text-sm text-gray-700">
                  <li>
                    Acesse{' '}
                    <a
                      href="https://ollama.com"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:underline"
                    >
                      ollama.com
                    </a>{' '}
                    e clique em "Download"
                  </li>
                  <li>Instale o programa como qualquer outro aplicativo</li>
                  <li>
                    Abra o Terminal e execute:{' '}
                    <code className="bg-gray-100 px-2 py-0.5 rounded font-mono text-xs">
                      ollama pull llama3.2
                    </code>
                  </li>
                  <li>Aguarde o download do modelo (pode demorar alguns minutos)</li>
                  <li>Pronto! Volte aqui e selecione o modelo</li>
                </ol>
              </div>
            )}
          </div>

          {/* URL config */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              URL do servidor Ollama
              <TooltipInfo text="Normalmente não é preciso alterar isso. Deixe o valor padrão se você instalou o Ollama no mesmo computador." />
            </label>
            <input
              type="text"
              className="input-field"
              value={localUrl}
              onChange={(e) => setLocalUrl(e.target.value)}
              placeholder="http://localhost:11434"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {LOCAL_MODELS.map((model) => (
              <StepCard
                key={model.id}
                selected={selectedModelId === model.id}
                onClick={() => handleLocalSelect(model)}
                badge={model.recommended ? '⭐ Mais leve' : undefined}
              >
                <div className="pt-1">
                  <h4 className="font-semibold text-gray-900">{model.name}</h4>
                  <p className="text-sm text-gray-500 mt-0.5">{model.description}</p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                      📦 {model.size}
                    </span>
                    <span className="text-xs text-gray-500">Velocidade: {model.speed}</span>
                  </div>
                </div>
              </StepCard>
            ))}
          </div>
        </div>
      )}

      {selectedModelId && (
        <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-green-700 text-sm font-medium">
          ✅ Modelo selecionado: {config.model?.model_name} ({config.model?.provider})
        </div>
      )}
    </div>
  )
}
