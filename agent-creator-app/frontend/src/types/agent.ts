export interface FrameworkConfig {
  id: string
  name: string
  description: string
  beginner_explanation: string
  recommended: boolean
  icon: string
  custom?: boolean
  custom_code?: string
}

export interface CharacteristicConfig {
  role: string
  role_label: string
  use_cases: string[]
  multi_agent: boolean
  sub_agent_roles?: string[]
}

export interface SkillConfig {
  id: string
  name: string
  description: string
  enabled: boolean
  icon: string
  complexity: 'easy' | 'medium' | 'hard'
  requires_config: boolean
  config?: Record<string, string>
}

export interface ModelConfig {
  provider: string
  model_id: string
  model_name: string
  api_key?: string
  local: boolean
  local_url?: string
  recommended: boolean
}

export interface MemoryConfig {
  type: 'none' | 'buffer' | 'semantic' | 'document'
  vector_store?: string
  document_paths?: string[]
}

export interface PersonaConfig {
  name: string
  avatar_emoji: string
  greeting: string
  tone: 'professional' | 'friendly' | 'casual' | 'direct'
  system_prompt: string
  language: 'pt-BR' | 'en-US' | 'es-ES'
}

export interface DeploymentConfig {
  targets: DeploymentTarget[]
}

export interface DeploymentTarget {
  type: 'telegram' | 'discord' | 'api' | 'widget' | 'whatsapp'
  enabled: boolean
  config: Record<string, string>
}

export interface AgentConfig {
  id?: string
  session_id: string
  framework: FrameworkConfig
  characteristics: CharacteristicConfig
  skills: SkillConfig[]
  model: ModelConfig
  memory: MemoryConfig
  persona: PersonaConfig
  deployment: DeploymentConfig
  created_at?: string
  updated_at?: string
  status?: 'draft' | 'ready' | 'paid'
}

export interface Template {
  id: string
  name: string
  description: string
  emoji: string
  category: string
  tags: string[]
  config: Partial<AgentConfig>
}

export interface CatalogItem {
  id: string
  name: string
  description: string
  beginner_explanation?: string
  recommended?: boolean
  icon?: string
  tags?: string[]
}

export interface ModelCatalogItem extends CatalogItem {
  provider: string
  local: boolean
  size_label?: string
  context_length?: number
}

export interface SkillCatalogItem extends CatalogItem {
  complexity: 'easy' | 'medium' | 'hard'
  requires_config: boolean
  config_fields?: ConfigField[]
}

export interface ConfigField {
  key: string
  label: string
  type: 'text' | 'password' | 'number' | 'select'
  placeholder?: string
  options?: string[]
  required?: boolean
}
