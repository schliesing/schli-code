from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class FrameworkConfig(BaseModel):
    id: str  # "langchain"|"crewai"|"autogen"|"llamaindex"|"custom"
    display_name: str
    version: str | None = None
    custom_install_cmd: str | None = None


class CharacteristicConfig(BaseModel):
    role: str  # "orchestrator"|"coder"|"debugger"|"researcher"|"customer_service"|"personal_assistant"|"custom"
    role_label: str
    is_multi_agent: bool = False
    sub_agents: list[str] = []


class SkillConfig(BaseModel):
    id: str
    enabled: bool = True
    config: dict[str, Any] = {}


class ModelConfig(BaseModel):
    provider: str  # "openai"|"anthropic"|"gemini"|"ollama"|"lmstudio"
    model_id: str
    api_key_env: str
    temperature: float = 0.7
    max_tokens: int = 2048
    base_url: str | None = None


class MemoryConfig(BaseModel):
    type: str  # "none"|"simple"|"semantic"|"vector_rag"
    vector_store: str | None = None
    embedding_model: str | None = None
    chunk_size: int = 512
    chunk_overlap: int = 64


class PersonaConfig(BaseModel):
    name: str
    avatar_emoji: str = "🤖"
    greeting: str
    system_prompt: str
    tone: str = "friendly"
    language: str = "pt"


class DeploymentConfig(BaseModel):
    targets: list[str] = []  # ["telegram","discord","rest_api","web_widget","whatsapp"]
    telegram_config: dict[str, Any] = {}
    discord_config: dict[str, Any] = {}
    whatsapp_config: dict[str, Any] = {}
    rest_api_config: dict[str, Any] = {}
    web_widget_config: dict[str, Any] = {}


class AgentConfigSchema(BaseModel):
    id: str | None = None
    user_session_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    framework: FrameworkConfig | None = None
    characteristics: CharacteristicConfig | None = None
    skills: list[SkillConfig] = []
    model: ModelConfig | None = None
    memory: MemoryConfig | None = None
    persona: PersonaConfig | None = None
    deployment: DeploymentConfig | None = None
    current_step: int = 0
    completed_steps: list[int] = []
    is_published: bool = False


class AgentCreateRequest(BaseModel):
    user_session_id: str


class AgentUpdateRequest(BaseModel):
    framework: FrameworkConfig | None = None
    characteristics: CharacteristicConfig | None = None
    skills: list[SkillConfig] | None = None
    model: ModelConfig | None = None
    memory: MemoryConfig | None = None
    persona: PersonaConfig | None = None
    deployment: DeploymentConfig | None = None
    current_step: int | None = None
    completed_steps: list[int] | None = None
    is_published: bool | None = None
    name: str | None = None
    is_draft: bool | None = None


class AgentListItem(BaseModel):
    id: str
    session_id: str
    name: str
    is_draft: bool
    created_at: datetime
    updated_at: datetime
    current_step: int
    completed_steps: list[int]
    is_published: bool
    framework_id: str | None = None
    role: str | None = None
    avatar_emoji: str | None = None

    model_config = {"from_attributes": True}


class AgentExportSchema(BaseModel):
    id: str
    agent_id: str
    payment_id: str | None
    download_token: str
    expires_at: datetime
    downloaded_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentIntentSchema(BaseModel):
    id: str
    agent_id: str
    session_id: str
    amount_cents: int
    currency: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportReadinessResponse(BaseModel):
    ready: bool
    missing: list[str]


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PaymentStatusResponse(BaseModel):
    agent_id: str
    paid: bool
    download_token: str | None = None
    expires_at: datetime | None = None
