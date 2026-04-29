import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, ArrowRight } from 'lucide-react'
import { listTemplates } from '../api/templates'
import { useAgentWizardStore } from '../store/agentWizardStore'
import type { Template } from '../types/agent'

const MOCK_TEMPLATES: Template[] = [
  { id: '1', name: 'Atendente Virtual', description: 'Responde dúvidas de clientes 24 horas por dia, 7 dias por semana, sem precisar de um atendente humano.', emoji: '💁', category: 'Atendimento', tags: ['atendimento', 'suporte', 'clientes'], config: {} },
  { id: '2', name: 'Assistente de Código', description: 'Ajuda a escrever, revisar e explicar código em qualquer linguagem de programação.', emoji: '👨‍💻', category: 'Tecnologia', tags: ['código', 'programação', 'dev'], config: {} },
  { id: '3', name: 'Pesquisador Web', description: 'Pesquisa e sintetiza informações da internet, resumindo tudo de forma clara e objetiva.', emoji: '🔬', category: 'Pesquisa', tags: ['pesquisa', 'web', 'resumos'], config: {} },
  { id: '4', name: 'Professor Particular', description: 'Explica qualquer assunto de forma didática e paciente, adaptando ao nível do aluno.', emoji: '📚', category: 'Educação', tags: ['educação', 'ensino', 'aprendizado'], config: {} },
  { id: '5', name: 'Analista de Dados', description: 'Analisa planilhas Excel, gera insights e cria relatórios automáticos dos seus dados.', emoji: '📊', category: 'Negócios', tags: ['dados', 'análise', 'relatórios'], config: {} },
  { id: '6', name: 'Assistente de Vendas', description: 'Qualifica leads, responde perguntas sobre produtos e auxilia no processo de vendas.', emoji: '💼', category: 'Vendas', tags: ['vendas', 'leads', 'comercial'], config: {} },
  { id: '7', name: 'Redator de Conteúdo', description: 'Cria posts para redes sociais, artigos de blog e textos de marketing profissionais.', emoji: '✍️', category: 'Marketing', tags: ['conteúdo', 'copywriting', 'marketing'], config: {} },
  { id: '8', name: 'Consultor Jurídico', description: 'Orienta sobre questões jurídicas básicas, analisa contratos e explica termos legais.', emoji: '⚖️', category: 'Jurídico', tags: ['direito', 'contratos', 'jurídico'], config: {} },
  { id: '9', name: 'Personal Trainer Virtual', description: 'Cria planos de treino personalizados e dá dicas de exercícios e alimentação saudável.', emoji: '🏋️', category: 'Saúde', tags: ['fitness', 'treino', 'saúde'], config: {} },
  { id: '10', name: 'Assistente de RH', description: 'Auxilia no recrutamento, analisa currículos e responde dúvidas de colaboradores.', emoji: '🤝', category: 'RH', tags: ['rh', 'recrutamento', 'pessoas'], config: {} },
  { id: '11', name: 'Bot de FAQ', description: 'Responde automaticamente as perguntas mais frequentes sobre seu produto ou serviço.', emoji: '❓', category: 'Atendimento', tags: ['faq', 'dúvidas', 'automação'], config: {} },
  { id: '12', name: 'Tradutor Profissional', description: 'Traduz textos para qualquer idioma preservando o contexto e tom original.', emoji: '🌐', category: 'Idiomas', tags: ['tradução', 'idiomas', 'linguagem'], config: {} },
]

const ALL_CATEGORIES = ['Todos', ...Array.from(new Set(MOCK_TEMPLATES.map((t) => t.category)))]

const CATEGORY_COLORS: Record<string, string> = {
  Atendimento: 'bg-blue-100 text-blue-700',
  Tecnologia: 'bg-purple-100 text-purple-700',
  Pesquisa: 'bg-green-100 text-green-700',
  Educação: 'bg-yellow-100 text-yellow-700',
  Negócios: 'bg-indigo-100 text-indigo-700',
  Vendas: 'bg-orange-100 text-orange-700',
  Marketing: 'bg-pink-100 text-pink-700',
  Jurídico: 'bg-gray-100 text-gray-700',
  Saúde: 'bg-red-100 text-red-700',
  RH: 'bg-teal-100 text-teal-700',
  Idiomas: 'bg-cyan-100 text-cyan-700',
}

export default function TemplatesGallery() {
  const [templates, setTemplates] = useState<Template[]>(MOCK_TEMPLATES)
  const [activeCategory, setActiveCategory] = useState('Todos')
  const [searchQuery, setSearchQuery] = useState('')
  const { updateConfig, resetWizard } = useAgentWizardStore()

  useEffect(() => {
    listTemplates()
      .then((data) => {
        if (data.length > 0) setTemplates(data)
      })
      .catch(() => {})
  }, [])

  function handleUseTemplate(template: Template) {
    resetWizard()
    if (template.config) {
      updateConfig(template.config)
    }
  }

  const filtered = templates.filter((t) => {
    const matchesCategory = activeCategory === 'Todos' || t.category === activeCategory
    const matchesSearch =
      !searchQuery ||
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.tags.some((tag) => tag.includes(searchQuery.toLowerCase()))
    return matchesCategory && matchesSearch
  })

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="text-center mb-10">
        <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-3">
          🗂️ Templates Prontos
        </h1>
        <p className="text-xl text-gray-500 max-w-2xl mx-auto">
          Escolha um template para começar mais rápido. Você pode personalizar tudo depois!
        </p>
      </div>

      {/* Search + Filters */}
      <div className="flex flex-col sm:flex-row gap-4 mb-8">
        {/* Search */}
        <div className="relative flex-1">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Pesquisar templates..."
            className="input-field pl-11"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Category filters - horizontal scroll on mobile */}
        <div className="flex gap-2 overflow-x-auto pb-1 sm:pb-0 shrink-0">
          {ALL_CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`shrink-0 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                activeCategory === cat
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'bg-white text-gray-600 border border-gray-200 hover:border-indigo-300'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Count */}
      <p className="text-sm text-gray-500 mb-5">
        {filtered.length} template{filtered.length !== 1 ? 's' : ''} encontrado
        {filtered.length !== 1 ? 's' : ''}
        {searchQuery && ` para "${searchQuery}"`}
      </p>

      {/* Grid */}
      {filtered.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {filtered.map((template) => (
            <div
              key={template.id}
              className="card hover:shadow-md transition-all duration-200 hover:-translate-y-0.5 flex flex-col"
            >
              {/* Emoji + Category */}
              <div className="flex items-start justify-between mb-4">
                <div className="w-16 h-16 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl flex items-center justify-center text-4xl">
                  {template.emoji}
                </div>
                <span
                  className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                    CATEGORY_COLORS[template.category] ?? 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {template.category}
                </span>
              </div>

              {/* Content */}
              <div className="flex-1">
                <h3 className="font-bold text-gray-900 text-lg mb-2">{template.name}</h3>
                <p className="text-sm text-gray-500 leading-relaxed mb-3">{template.description}</p>

                {/* Tags */}
                <div className="flex flex-wrap gap-1.5">
                  {template.tags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => setSearchQuery(tag)}
                      className="text-xs text-gray-400 hover:text-indigo-600 bg-gray-50 hover:bg-indigo-50 px-2 py-0.5 rounded-full transition-colors"
                    >
                      #{tag}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action */}
              <Link
                to="/wizard"
                onClick={() => handleUseTemplate(template)}
                className="mt-5 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-sm py-3 rounded-xl transition-colors shadow-sm"
              >
                Usar este template
                <ArrowRight size={16} />
              </Link>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-20">
          <div className="text-5xl mb-4">🔍</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">Nenhum template encontrado</h3>
          <p className="text-gray-500 mb-6">
            Tente uma busca diferente ou explore todas as categorias.
          </p>
          <button
            type="button"
            onClick={() => { setSearchQuery(''); setActiveCategory('Todos') }}
            className="btn-secondary"
          >
            Limpar filtros
          </button>
        </div>
      )}

      {/* Create from scratch CTA */}
      <div className="mt-12 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-100 rounded-2xl p-8 text-center">
        <h3 className="text-2xl font-bold text-gray-900 mb-2">
          Não encontrou o que procura? ✨
        </h3>
        <p className="text-gray-500 mb-6">
          Crie seu agente do zero com nosso wizard guiado. Leva menos de 10 minutos!
        </p>
        <Link
          to="/wizard"
          onClick={useAgentWizardStore.getState().resetWizard}
          className="btn-primary inline-flex items-center gap-2"
        >
          <span>🤖</span>
          Criar do Zero
          <ArrowRight size={18} />
        </Link>
      </div>
    </div>
  )
}
