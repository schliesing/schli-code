"""
Pre-built agent configuration templates.
All user-facing strings are in Portuguese (pt-BR).
"""

TEMPLATES = [
    {
        "id": "customer-service-bot",
        "name": "Bot de Atendimento ao Cliente",
        "description": "Um atendente virtual simpático que responde perguntas dos seus clientes 24h por dia, busca informações na web e opera via Telegram.",
        "icon_emoji": "🎧",
        "tags": ["atendimento", "telegram", "iniciante", "negócios"],
        "complexity": "beginner",
        "config": {
            "framework": {
                "id": "langchain",
                "display_name": "LangChain",
                "version": "0.2.x",
            },
            "characteristics": {
                "role": "customer_service",
                "role_label": "Atendente",
                "is_multi_agent": False,
                "sub_agents": [],
            },
            "skills": [
                {"id": "web_search", "enabled": True, "config": {}},
                {"id": "datetime", "enabled": True, "config": {}},
            ],
            "model": {
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
                "temperature": 0.7,
                "max_tokens": 1024,
            },
            "memory": {
                "type": "simple",
                "vector_store": None,
                "embedding_model": None,
                "chunk_size": 512,
                "chunk_overlap": 64,
            },
            "persona": {
                "name": "Atendy",
                "avatar_emoji": "🎧",
                "greeting": "Olá! Sou o Atendy, seu assistente virtual. Como posso te ajudar hoje?",
                "system_prompt": (
                    "Você é Atendy, um atendente virtual simpático e prestativo. "
                    "Seu objetivo é ajudar os clientes com suas dúvidas de forma clara e amigável. "
                    "Sempre responda em português brasileiro. "
                    "Se não souber algo, pesquise na web antes de responder. "
                    "Seja conciso mas completo nas respostas."
                ),
                "tone": "friendly",
                "language": "pt",
            },
            "deployment": {
                "targets": ["telegram"],
                "telegram_config": {
                    "parse_mode": "HTML",
                    "enable_markdown": True,
                },
                "discord_config": {},
                "whatsapp_config": {},
                "rest_api_config": {},
                "web_widget_config": {},
            },
            "current_step": 6,
            "completed_steps": [0, 1, 2, 3, 4, 5, 6],
            "is_published": False,
        },
    },
    {
        "id": "coding-assistant",
        "name": "Assistente de Programação",
        "description": "Um programador virtual que escreve código Python, lê arquivos e executa scripts para automatizar suas tarefas.",
        "icon_emoji": "💻",
        "tags": ["programação", "python", "automação", "intermediário"],
        "complexity": "intermediate",
        "config": {
            "framework": {
                "id": "langchain",
                "display_name": "LangChain",
                "version": "0.2.x",
            },
            "characteristics": {
                "role": "coder",
                "role_label": "Programador",
                "is_multi_agent": False,
                "sub_agents": [],
            },
            "skills": [
                {"id": "code_execution", "enabled": True, "config": {}},
                {"id": "file_read", "enabled": True, "config": {}},
                {"id": "calculator", "enabled": True, "config": {}},
            ],
            "model": {
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
                "temperature": 0.2,
                "max_tokens": 4096,
            },
            "memory": {
                "type": "simple",
                "vector_store": None,
                "embedding_model": None,
                "chunk_size": 512,
                "chunk_overlap": 64,
            },
            "persona": {
                "name": "CodeBot",
                "avatar_emoji": "💻",
                "greeting": "Olá! Sou o CodeBot, seu assistente de programação. Me diga o que você precisa criar ou automatizar!",
                "system_prompt": (
                    "Você é CodeBot, um programador Python experiente e paciente. "
                    "Você escreve código limpo, bem documentado e funcional. "
                    "Sempre explique o que o código faz em linguagem simples. "
                    "Quando executar código, mostre a saída e explique os resultados. "
                    "Responda sempre em português brasileiro."
                ),
                "tone": "technical",
                "language": "pt",
            },
            "deployment": {
                "targets": ["rest_api", "web_widget"],
                "telegram_config": {},
                "discord_config": {},
                "whatsapp_config": {},
                "rest_api_config": {"port": 8000, "enable_cors": True},
                "web_widget_config": {"theme": "dark", "position": "bottom-right"},
            },
            "current_step": 6,
            "completed_steps": [0, 1, 2, 3, 4, 5, 6],
            "is_published": False,
        },
    },
    {
        "id": "research-assistant",
        "name": "Assistente de Pesquisa",
        "description": "Um pesquisador virtual que busca informações atualizadas na web, analisa documentos e cria resumos detalhados.",
        "icon_emoji": "🔬",
        "tags": ["pesquisa", "resumo", "documentos", "intermediário"],
        "complexity": "intermediate",
        "config": {
            "framework": {
                "id": "langchain",
                "display_name": "LangChain",
                "version": "0.2.x",
            },
            "characteristics": {
                "role": "researcher",
                "role_label": "Pesquisador",
                "is_multi_agent": False,
                "sub_agents": [],
            },
            "skills": [
                {"id": "web_search", "enabled": True, "config": {}},
                {"id": "file_read", "enabled": True, "config": {}},
                {"id": "datetime", "enabled": True, "config": {}},
            ],
            "model": {
                "provider": "anthropic",
                "model_id": "claude-sonnet-4-6",
                "api_key_env": "ANTHROPIC_API_KEY",
                "temperature": 0.5,
                "max_tokens": 4096,
            },
            "memory": {
                "type": "vector_rag",
                "vector_store": "chroma",
                "embedding_model": "text-embedding-3-small",
                "chunk_size": 1000,
                "chunk_overlap": 200,
            },
            "persona": {
                "name": "ResearchPro",
                "avatar_emoji": "🔬",
                "greeting": "Olá! Sou o ResearchPro. Me diga o que você quer pesquisar e eu encontrarei as informações mais relevantes para você!",
                "system_prompt": (
                    "Você é ResearchPro, um assistente de pesquisa especializado e meticuloso. "
                    "Você busca informações de múltiplas fontes, verifica fatos e cria resumos claros e bem estruturados. "
                    "Sempre cite as fontes das informações encontradas. "
                    "Organize suas respostas com títulos e listas quando apropriado. "
                    "Responda sempre em português brasileiro com linguagem clara e acessível."
                ),
                "tone": "professional",
                "language": "pt",
            },
            "deployment": {
                "targets": ["web_widget", "rest_api"],
                "telegram_config": {},
                "discord_config": {},
                "whatsapp_config": {},
                "rest_api_config": {"port": 8000, "enable_cors": True},
                "web_widget_config": {"theme": "light", "position": "bottom-right"},
            },
            "current_step": 6,
            "completed_steps": [0, 1, 2, 3, 4, 5, 6],
            "is_published": False,
        },
    },
    {
        "id": "personal-telegram-bot",
        "name": "Bot Pessoal no Telegram",
        "description": "Seu assistente pessoal no Telegram, rodando 100% localmente no seu computador — sem custo com APIs externas.",
        "icon_emoji": "🌟",
        "tags": ["pessoal", "telegram", "local", "gratuito", "iniciante"],
        "complexity": "beginner",
        "config": {
            "framework": {
                "id": "langchain",
                "display_name": "LangChain",
                "version": "0.2.x",
            },
            "characteristics": {
                "role": "personal_assistant",
                "role_label": "Assistente Pessoal",
                "is_multi_agent": False,
                "sub_agents": [],
            },
            "skills": [
                {"id": "web_search", "enabled": True, "config": {}},
                {"id": "calculator", "enabled": True, "config": {}},
                {"id": "datetime", "enabled": True, "config": {}},
            ],
            "model": {
                "provider": "ollama",
                "model_id": "llama3.2:1b",
                "api_key_env": "",
                "temperature": 0.7,
                "max_tokens": 2048,
                "base_url": "http://localhost:11434",
            },
            "memory": {
                "type": "simple",
                "vector_store": None,
                "embedding_model": None,
                "chunk_size": 512,
                "chunk_overlap": 64,
            },
            "persona": {
                "name": "Meu Assistente",
                "avatar_emoji": "🌟",
                "greeting": "Oi! Sou seu assistente pessoal. Pode me perguntar qualquer coisa!",
                "system_prompt": (
                    "Você é um assistente pessoal amigável e prestativo. "
                    "Você ajuda com pesquisas na web, cálculos, informações sobre data e hora, "
                    "e qualquer outra tarefa do dia a dia. "
                    "Seja sempre simpático, conciso e útil. "
                    "Responda em português brasileiro."
                ),
                "tone": "friendly",
                "language": "pt",
            },
            "deployment": {
                "targets": ["telegram"],
                "telegram_config": {
                    "parse_mode": "HTML",
                    "enable_markdown": True,
                },
                "discord_config": {},
                "whatsapp_config": {},
                "rest_api_config": {},
                "web_widget_config": {},
            },
            "current_step": 6,
            "completed_steps": [0, 1, 2, 3, 4, 5, 6],
            "is_published": False,
        },
    },
    {
        "id": "sql-analyst",
        "name": "Analista de Dados SQL",
        "description": "Um analista de dados que escreve consultas SQL, analisa datasets em Python e gera insights sobre seus dados.",
        "icon_emoji": "📊",
        "tags": ["dados", "sql", "análise", "python", "intermediário"],
        "complexity": "intermediate",
        "config": {
            "framework": {
                "id": "langchain",
                "display_name": "LangChain",
                "version": "0.2.x",
            },
            "characteristics": {
                "role": "coder",
                "role_label": "Programador",
                "is_multi_agent": False,
                "sub_agents": [],
            },
            "skills": [
                {"id": "code_execution", "enabled": True, "config": {}},
                {"id": "file_read", "enabled": True, "config": {}},
                {"id": "calculator", "enabled": True, "config": {}},
            ],
            "model": {
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
                "temperature": 0.1,
                "max_tokens": 4096,
            },
            "memory": {
                "type": "simple",
                "vector_store": None,
                "embedding_model": None,
                "chunk_size": 512,
                "chunk_overlap": 64,
            },
            "persona": {
                "name": "DataBot",
                "avatar_emoji": "📊",
                "greeting": "Olá! Sou o DataBot, seu analista de dados. Compartilhe seus dados ou descreva sua análise e eu ajudo!",
                "system_prompt": (
                    "Você é DataBot, um analista de dados especializado em Python, pandas, SQL e visualizações. "
                    "Você analisa datasets, escreve consultas SQL, cria scripts pandas e gera insights claros. "
                    "Sempre explique sua análise em linguagem simples para quem não é técnico. "
                    "Quando escrever código, execute-o e mostre os resultados. "
                    "Prefira criar visualizações quando os dados permitirem. "
                    "Responda sempre em português brasileiro."
                ),
                "tone": "professional",
                "language": "pt",
            },
            "deployment": {
                "targets": ["web_widget", "rest_api"],
                "telegram_config": {},
                "discord_config": {},
                "whatsapp_config": {},
                "rest_api_config": {"port": 8000, "enable_cors": True},
                "web_widget_config": {"theme": "light", "position": "bottom-right"},
            },
            "current_step": 6,
            "completed_steps": [0, 1, 2, 3, 4, 5, 6],
            "is_published": False,
        },
    },
    {
        "id": "discord-community-bot",
        "name": "Bot de Comunidade Discord",
        "description": "Um bot animado para sua comunidade Discord: responde dúvidas, busca informações na web e mantém a galera engajada.",
        "icon_emoji": "🎮",
        "tags": ["discord", "comunidade", "entretenimento", "intermediário"],
        "complexity": "intermediate",
        "config": {
            "framework": {
                "id": "langchain",
                "display_name": "LangChain",
                "version": "0.2.x",
            },
            "characteristics": {
                "role": "customer_service",
                "role_label": "Atendente",
                "is_multi_agent": False,
                "sub_agents": [],
            },
            "skills": [
                {"id": "web_search", "enabled": True, "config": {}},
                {"id": "datetime", "enabled": True, "config": {}},
            ],
            "model": {
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "api_key_env": "OPENAI_API_KEY",
                "temperature": 0.8,
                "max_tokens": 1024,
            },
            "memory": {
                "type": "none",
                "vector_store": None,
                "embedding_model": None,
                "chunk_size": 512,
                "chunk_overlap": 64,
            },
            "persona": {
                "name": "DiscordHelper",
                "avatar_emoji": "🎮",
                "greeting": "Eae galera! Sou o DiscordHelper, pode me chamar pra qualquer dúvida ou papo! 🎮",
                "system_prompt": (
                    "Você é DiscordHelper, um bot animado e descontraído para uma comunidade Discord. "
                    "Você responde perguntas, busca informações na web quando necessário, "
                    "e mantém um tom divertido e inclusivo. "
                    "Use emojis com moderação para deixar as mensagens mais animadas. "
                    "Seja respeitoso e incentive a comunidade positiva. "
                    "Responda em português brasileiro com linguagem informal e jovial."
                ),
                "tone": "casual",
                "language": "pt",
            },
            "deployment": {
                "targets": ["discord"],
                "telegram_config": {},
                "discord_config": {
                    "command_prefix": "!",
                    "enable_slash_commands": True,
                    "respond_to_mentions": True,
                },
                "whatsapp_config": {},
                "rest_api_config": {},
                "web_widget_config": {},
            },
            "current_step": 6,
            "completed_steps": [0, 1, 2, 3, 4, 5, 6],
            "is_published": False,
        },
    },
]

# Template index for quick lookup
TEMPLATE_INDEX = {t["id"]: t for t in TEMPLATES}
