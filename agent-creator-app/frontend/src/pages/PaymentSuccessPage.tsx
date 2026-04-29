import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Download, ChevronDown, ChevronUp, CheckCircle, Home } from 'lucide-react'
import { exportAgent } from '../api/agents'

const INSTALL_STEPS = [
  {
    title: '1. Instale o Python',
    icon: '🐍',
    description: 'Baixe e instale o Python 3.11+ em python.org',
    detail: `1. Acesse python.org/downloads\n2. Clique em "Download Python 3.x.x"\n3. Execute o instalador\n4. ✅ Marque "Add Python to PATH"\n5. Clique em "Install Now"`,
  },
  {
    title: '2. Extraia o pacote',
    icon: '📦',
    description: 'Descompacte o arquivo ZIP que você baixou',
    detail: `1. Clique com o botão direito no arquivo ZIP\n2. Selecione "Extrair tudo..."\n3. Escolha uma pasta (ex: Área de Trabalho)\n4. Clique em "Extrair"`,
  },
  {
    title: '3. Instale as dependências',
    icon: '⚙️',
    description: 'Execute o script de instalação automática',
    detail: `1. Abra a pasta extraída\n2. Clique duas vezes em "instalar.bat" (Windows) ou execute:\n   cd pasta-do-agente\n   pip install -r requirements.txt`,
  },
  {
    title: '4. Configure as credenciais',
    icon: '🔑',
    description: 'Adicione suas chaves de API no arquivo .env',
    detail: `1. Abra o arquivo ".env" com o Bloco de Notas\n2. Preencha as informações (API keys, tokens, etc.)\n3. Salve o arquivo\nObs: Este arquivo já vem preenchido com as configurações que você inseriu no wizard!`,
  },
  {
    title: '5. Execute seu agente',
    icon: '🚀',
    description: 'Inicie seu agente com um simples comando',
    detail: `1. Abra o terminal/prompt na pasta do agente\n2. Execute: python main.py\n3. Seu agente estará online! 🎉\n\nPara Telegram: seu bot estará disponível imediatamente\nPara Widget: copie o código do terminal e cole no seu site`,
  },
]

export default function PaymentSuccessPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const agentId = searchParams.get('agent_id')
  const [expandedStep, setExpandedStep] = useState<number | null>(0)
  const [isDownloading, setIsDownloading] = useState(false)
  const [showAnimation, setShowAnimation] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => setShowAnimation(false), 3000)
    return () => clearTimeout(timer)
  }, [])

  async function handleDownload() {
    if (!token) {
      alert('Link de download inválido. Por favor, entre em contato com o suporte.')
      return
    }
    setIsDownloading(true)
    try {
      const blob = await exportAgent(token)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'meu-agente.zip'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Erro ao baixar o agente. Por favor, tente novamente ou entre em contato com o suporte.')
    } finally {
      setIsDownloading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-indigo-50 flex flex-col items-center justify-start py-12 px-4">
      <div className="w-full max-w-2xl">
        {/* Success animation */}
        <div className="text-center mb-10">
          <div
            className={`w-28 h-28 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6 ${
              showAnimation ? 'animate-checkmark' : ''
            }`}
          >
            <CheckCircle
              size={64}
              className="text-green-500"
              strokeWidth={1.5}
            />
          </div>

          <div className="inline-flex items-center gap-2 bg-green-100 text-green-700 text-sm font-semibold px-4 py-1.5 rounded-full mb-4">
            ✅ Pagamento confirmado
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 mb-3">
            Seu agente está pronto! 🎉
          </h1>
          <p className="text-xl text-gray-500 max-w-lg mx-auto">
            Parabéns! Você criou seu primeiro agente de IA. Agora é só baixar e instalar.
          </p>
        </div>

        {/* Download button */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8 mb-6">
          <div className="text-center mb-6">
            <div className="text-5xl mb-3">📦</div>
            <h2 className="text-2xl font-bold text-gray-900 mb-1">Seu pacote está pronto</h2>
            <p className="text-gray-500">
              Inclui: código do agente, dependências, instruções e configurações
            </p>
          </div>

          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading || !token}
            className={`w-full flex items-center justify-center gap-3 font-bold text-lg py-5 rounded-2xl transition-all shadow-md ${
              !token
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-green-600 hover:bg-green-700 text-white hover:shadow-xl active:scale-98'
            } ${isDownloading ? 'opacity-70 cursor-wait' : ''}`}
          >
            <Download size={24} />
            {isDownloading ? 'Preparando download...' : 'Baixar meu Agente'}
          </button>

          {!token && (
            <p className="text-center text-sm text-gray-400 mt-3">
              Link de download não encontrado. Verifique seu e-mail ou entre em contato com o suporte.
            </p>
          )}

          <p className="text-center text-xs text-gray-400 mt-4">
            O link de download é válido por 30 dias • Você pode baixar até 5 vezes
          </p>
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          {agentId && (
            <Link
              to={`/test/${agentId}`}
              className="flex flex-col items-center gap-2 bg-white border border-gray-100 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all text-center"
            >
              <span className="text-3xl">🧪</span>
              <span className="font-semibold text-gray-900">Testar novamente</span>
              <span className="text-xs text-gray-400">Converse com seu agente</span>
            </Link>
          )}
          <Link
            to="/dashboard"
            className="flex flex-col items-center gap-2 bg-white border border-gray-100 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all text-center"
          >
            <span className="text-3xl">🗂️</span>
            <span className="font-semibold text-gray-900">Meus Agentes</span>
            <span className="text-xs text-gray-400">Ver todos os agentes</span>
          </Link>
          <Link
            to="/wizard"
            className="flex flex-col items-center gap-2 bg-white border border-gray-100 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all text-center"
          >
            <span className="text-3xl">🤖</span>
            <span className="font-semibold text-gray-900">Criar outro agente</span>
            <span className="text-xs text-gray-400">Novo wizard</span>
          </Link>
          <Link
            to="/"
            className="flex flex-col items-center gap-2 bg-white border border-gray-100 rounded-2xl p-5 shadow-sm hover:shadow-md transition-all text-center"
          >
            <Home size={28} className="text-gray-400" />
            <span className="font-semibold text-gray-900">Página inicial</span>
            <span className="text-xs text-gray-400">Voltar ao início</span>
          </Link>
        </div>

        {/* Installation guide */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-5 border-b border-gray-100">
            <h3 className="text-xl font-bold text-gray-900">
              📋 Como instalar seu agente
            </h3>
            <p className="text-gray-500 text-sm mt-1">
              Siga o passo a passo abaixo. Leva menos de 15 minutos!
            </p>
          </div>

          <div className="divide-y divide-gray-100">
            {INSTALL_STEPS.map((step, idx) => (
              <div key={idx}>
                <button
                  type="button"
                  onClick={() => setExpandedStep(expandedStep === idx ? null : idx)}
                  className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{step.icon}</span>
                    <div>
                      <p className="font-semibold text-gray-900">{step.title}</p>
                      <p className="text-sm text-gray-500 mt-0.5">{step.description}</p>
                    </div>
                  </div>
                  {expandedStep === idx ? (
                    <ChevronUp size={18} className="text-gray-400 shrink-0" />
                  ) : (
                    <ChevronDown size={18} className="text-gray-400 shrink-0" />
                  )}
                </button>

                {expandedStep === idx && (
                  <div className="px-6 pb-5 bg-gray-50 border-t border-gray-100 animate-fade-in">
                    <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed mt-3">
                      {step.detail}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Support */}
        <div className="text-center mt-8 text-sm text-gray-400">
          <p>
            Precisa de ajuda?{' '}
            <a href="mailto:suporte@criabot.com.br" className="text-indigo-600 hover:underline">
              suporte@criabot.com.br
            </a>{' '}
            — respondemos em até 24 horas
          </p>
        </div>
      </div>
    </div>
  )
}
