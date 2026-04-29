import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Zap, Shield, Download } from 'lucide-react'
import { listTemplates } from '../api/templates'
import type { Template } from '../types/agent'

const MOCK_TEMPLATES: Template[] = [
  { id: '1', name: 'Atendente Virtual', description: 'Responde dúvidas de clientes 24/7', emoji: '💁', category: 'Atendimento', tags: ['atendimento', 'suporte'], config: {} },
  { id: '2', name: 'Assistente de Código', description: 'Ajuda a programar em qualquer linguagem', emoji: '👨‍💻', category: 'Tecnologia', tags: ['código', 'dev'], config: {} },
  { id: '3', name: 'Pesquisador Web', description: 'Busca e sintetiza informações da internet', emoji: '🔬', category: 'Pesquisa', tags: ['pesquisa', 'web'], config: {} },
  { id: '4', name: 'Professor Particular', description: 'Explica qualquer assunto de forma didática', emoji: '📚', category: 'Educação', tags: ['educação', 'ensino'], config: {} },
  { id: '5', name: 'Analista de Dados', description: 'Analisa planilhas e gera insights', emoji: '📊', category: 'Negócios', tags: ['dados', 'análise'], config: {} },
  { id: '6', name: 'Assistente de Vendas', description: 'Qualifica leads e auxilia no funil de vendas', emoji: '💼', category: 'Vendas', tags: ['vendas', 'crm'], config: {} },
]

const TESTIMONIALS = [
  {
    name: 'Maria Silva',
    role: 'Dona de loja online',
    avatar: '👩',
    text: 'Em 10 minutos criei um atendente virtual para minha loja. Meus clientes adoraram!',
  },
  {
    name: 'João Pereira',
    role: 'Desenvolvedor freelancer',
    avatar: '👨‍💻',
    text: 'O agente de código me economiza horas todos os dias. Vale muito o investimento.',
  },
  {
    name: 'Ana Costa',
    role: 'Professora universitária',
    avatar: '👩‍🏫',
    text: 'Criei um assistente de estudos para meus alunos sem saber programar. Incrível!',
  },
]

const FEATURES = [
  {
    icon: '🧙',
    title: 'Assistente guiado passo a passo',
    description: 'Nosso wizard te guia em cada detalhe, com explicações simples para quem nunca usou IA antes.',
  },
  {
    icon: '🧪',
    title: 'Teste antes de comprar',
    description: 'Converse com seu agente em tempo real antes de finalizar. Garanta que é exatamente o que você precisa.',
  },
  {
    icon: '📦',
    title: 'Receba o pacote pronto para instalar',
    description: 'Após a configuração, você baixa um pacote completo e pronto para rodar — sem dor de cabeça.',
  },
]

export default function LandingPage() {
  const [templates, setTemplates] = useState<Template[]>(MOCK_TEMPLATES)

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates(MOCK_TEMPLATES))
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-indigo-900 via-indigo-800 to-purple-900 text-white">
        <div className="absolute inset-0 bg-grid-white/[0.05] bg-[size:30px_30px]" />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-24 sm:py-32">
          <div className="text-center max-w-4xl mx-auto">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 rounded-full px-4 py-1.5 text-sm font-medium text-indigo-200 mb-8">
              <Zap size={14} className="text-yellow-400" />
              Sem precisar saber programar
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-tight mb-6">
              Crie seu Agente de IA{' '}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-yellow-400 to-orange-400">
                em minutos
              </span>
            </h1>

            {/* Subheadline */}
            <p className="text-xl sm:text-2xl text-indigo-200 mb-10 max-w-3xl mx-auto leading-relaxed">
              Sem precisar saber programar. Configure, teste e receba seu agente pronto para usar.
            </p>

            {/* CTA */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Link
                to="/wizard"
                className="flex items-center gap-3 bg-white text-indigo-700 font-bold text-lg px-8 py-4 rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0"
              >
                <span className="text-2xl">🤖</span>
                Criar meu Agente
                <ArrowRight size={20} />
              </Link>
              <Link
                to="/templates"
                className="flex items-center gap-2 text-indigo-200 hover:text-white font-semibold text-lg border border-white/30 px-6 py-4 rounded-2xl hover:border-white/60 transition-all"
              >
                Ver templates prontos →
              </Link>
            </div>

            {/* Social proof */}
            <p className="text-indigo-300 text-sm mt-8">
              🎉 Mais de 1.200 agentes criados por iniciantes como você
            </p>
          </div>
        </div>

        {/* Wave separator */}
        <div className="absolute bottom-0 left-0 right-0">
          <svg viewBox="0 0 1440 60" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0,60 C360,0 1080,0 1440,60 L1440,60 L0,60 Z" fill="#F9FAFB" />
          </svg>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            Como funciona?
          </h2>
          <p className="text-xl text-gray-500">
            Em apenas 3 passos simples, seu agente está pronto
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {FEATURES.map((feature, idx) => (
            <div key={idx} className="card text-center hover:shadow-md transition-shadow">
              <div className="w-20 h-20 bg-indigo-50 rounded-2xl flex items-center justify-center text-4xl mx-auto mb-5">
                {feature.icon}
              </div>
              <div className="flex items-center justify-center gap-2 mb-3">
                <span className="w-7 h-7 bg-indigo-600 text-white text-sm font-bold rounded-full flex items-center justify-center">
                  {idx + 1}
                </span>
                <h3 className="font-bold text-gray-900 text-lg">{feature.title}</h3>
              </div>
              <p className="text-gray-500 leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Templates preview */}
      <section className="bg-white py-20">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-end justify-between mb-10">
            <div>
              <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-2">
                Templates prontos para usar
              </h2>
              <p className="text-gray-500">Comece com um template e personalize como quiser</p>
            </div>
            <Link
              to="/templates"
              className="hidden sm:flex items-center gap-1.5 text-indigo-600 hover:text-indigo-800 font-semibold"
            >
              Ver todos <ArrowRight size={16} />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {templates.slice(0, 6).map((template) => (
              <div
                key={template.id}
                className="card hover:shadow-md transition-all hover:-translate-y-0.5 group cursor-pointer"
              >
                <div className="flex items-start gap-4">
                  <div className="w-14 h-14 bg-indigo-50 rounded-xl flex items-center justify-center text-3xl shrink-0">
                    {template.emoji}
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                      {template.category}
                    </span>
                    <h3 className="font-bold text-gray-900 mt-1.5">{template.name}</h3>
                    <p className="text-sm text-gray-500 mt-1">{template.description}</p>
                  </div>
                </div>
                <Link
                  to="/wizard"
                  className="mt-4 flex items-center justify-center gap-2 w-full bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white font-semibold text-sm py-2.5 rounded-xl transition-all duration-200"
                >
                  Usar este template <ArrowRight size={14} />
                </Link>
              </div>
            ))}
          </div>

          <div className="text-center mt-8 sm:hidden">
            <Link to="/templates" className="btn-secondary">
              Ver todos os templates →
            </Link>
          </div>
        </div>
      </section>

      {/* Benefits bar */}
      <section className="bg-indigo-600 py-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 text-center text-white">
            <div className="flex flex-col items-center gap-2">
              <Shield size={32} className="text-indigo-200" />
              <h3 className="font-bold text-lg">Sem contrato</h3>
              <p className="text-indigo-200 text-sm">Pague uma vez, use para sempre. Sem mensalidade.</p>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Download size={32} className="text-indigo-200" />
              <h3 className="font-bold text-lg">Código seu</h3>
              <p className="text-indigo-200 text-sm">Você recebe o código fonte completo, 100% seu.</p>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Zap size={32} className="text-indigo-200" />
              <h3 className="font-bold text-lg">Suporte incluído</h3>
              <p className="text-indigo-200 text-sm">Dúvidas? Nossa equipe te ajuda a instalar.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-4">
            O que nossos clientes dizem
          </h2>
          <div className="flex items-center justify-center gap-1 text-yellow-400 text-xl">
            {'★'.repeat(5)}
            <span className="text-gray-500 text-base ml-2">4.9/5 de 300+ avaliações</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {TESTIMONIALS.map((t, idx) => (
            <div key={idx} className="card hover:shadow-md transition-shadow">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 bg-indigo-100 rounded-full flex items-center justify-center text-2xl">
                  {t.avatar}
                </div>
                <div>
                  <p className="font-bold text-gray-900">{t.name}</p>
                  <p className="text-sm text-gray-500">{t.role}</p>
                </div>
              </div>
              <div className="flex text-yellow-400 mb-3 text-sm">{'★'.repeat(5)}</div>
              <p className="text-gray-700 italic">"{t.text}"</p>
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="bg-gradient-to-r from-indigo-600 to-purple-700 py-20">
        <div className="max-w-3xl mx-auto px-4 text-center text-white">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">
            Pronto para criar seu agente? 🚀
          </h2>
          <p className="text-xl text-indigo-200 mb-8">
            Leva menos de 10 minutos e você pode testar de graça antes de pagar.
          </p>
          <Link
            to="/wizard"
            className="inline-flex items-center gap-3 bg-white text-indigo-700 font-bold text-xl px-10 py-5 rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 hover:-translate-y-0.5"
          >
            <span>🤖</span>
            Criar meu Agente Agora
            <ArrowRight size={22} />
          </Link>
          <p className="text-indigo-300 text-sm mt-4">Grátis para testar • R$ 9,99 para baixar</p>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <span className="text-2xl">🤖</span>
              <span className="font-bold text-white text-xl">CriaBot</span>
            </div>
            <div className="flex gap-6 text-sm">
              <Link to="/templates" className="hover:text-white transition-colors">Templates</Link>
              <Link to="/dashboard" className="hover:text-white transition-colors">Meus Agentes</Link>
              <a href="#" className="hover:text-white transition-colors">Suporte</a>
            </div>
            <p className="text-sm">© 2026 CriaBot. Feito com ❤️ no Brasil.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
