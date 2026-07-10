"""
AgentBuilder: Converts an AgentConfigSchema into a runnable LangChain agent.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

try:
    # langchain >= 1.0 reorganized classic components
    from langchain_classic.agents import AgentExecutor, create_react_agent
    from langchain_classic.memory import ConversationBufferMemory, ConversationSummaryMemory
    from langchain_classic.prompts import PromptTemplate
    from langchain_classic.tools import Tool
except ImportError:
    # Fallback for langchain 0.2.x
    from langchain.agents import AgentExecutor, create_react_agent  # type: ignore[no-redef]
    from langchain.memory import ConversationBufferMemory, ConversationSummaryMemory  # type: ignore[no-redef]
    from langchain.prompts import PromptTemplate  # type: ignore[no-redef]
    from langchain.tools import Tool  # type: ignore[no-redef]
from langchain_core.language_models import BaseChatModel

from app.schemas.agent import AgentConfigSchema, ModelConfig, MemoryConfig


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def _build_llm(model_cfg: ModelConfig) -> BaseChatModel:
    provider = model_cfg.provider

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise RuntimeError(
                "O pacote 'langchain-openai' não está instalado. "
                "Execute: pip install langchain-openai"
            )
        api_key = os.environ.get(model_cfg.api_key_env, "")
        if not api_key:
            # Use dummy key so the agent can be instantiated for testing
            api_key = "sk-dummy-key-for-testing"
        return ChatOpenAI(
            model=model_cfg.model_id,
            temperature=model_cfg.temperature,
            max_tokens=model_cfg.max_tokens,
            api_key=api_key,
            streaming=True,
        )

    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise RuntimeError(
                "O pacote 'langchain-anthropic' não está instalado. "
                "Execute: pip install langchain-anthropic"
            )
        api_key = os.environ.get(model_cfg.api_key_env, "")
        if not api_key:
            api_key = "sk-ant-dummy-key-for-testing"
        return ChatAnthropic(
            model=model_cfg.model_id,
            temperature=model_cfg.temperature,
            max_tokens=model_cfg.max_tokens,
            api_key=api_key,
            streaming=True,
        )

    elif provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise RuntimeError(
                "O pacote 'langchain-google-genai' não está instalado. "
                "Execute: pip install langchain-google-genai"
            )
        api_key = os.environ.get(model_cfg.api_key_env, "")
        if not api_key:
            api_key = "dummy-key-for-testing"
        return ChatGoogleGenerativeAI(
            model=model_cfg.model_id,
            temperature=model_cfg.temperature,
            max_output_tokens=model_cfg.max_tokens,
            google_api_key=api_key,
        )

    elif provider == "ollama":
        try:
            from langchain_community.chat_models import ChatOllama
        except ImportError:
            raise RuntimeError(
                "O pacote 'langchain-community' não está instalado. "
                "Execute: pip install langchain-community"
            )
        base_url = model_cfg.base_url or "http://localhost:11434"
        return ChatOllama(
            model=model_cfg.model_id,
            base_url=base_url,
            temperature=model_cfg.temperature,
        )

    elif provider == "lmstudio":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise RuntimeError(
                "O pacote 'langchain-openai' não está instalado. "
                "Execute: pip install langchain-openai"
            )
        base_url = model_cfg.base_url or "http://localhost:1234/v1"
        return ChatOpenAI(
            model=model_cfg.model_id,
            base_url=base_url,
            api_key="lm-studio",  # LM Studio ignores the key
            temperature=model_cfg.temperature,
            max_tokens=model_cfg.max_tokens,
            streaming=True,
        )

    else:
        raise ValueError(
            f"Provedor de modelo desconhecido: '{provider}'. "
            f"Provedores suportados: openai, anthropic, gemini, ollama, lmstudio"
        )


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------

def _build_tools(skills: list) -> list[Tool]:
    tools: list[Tool] = []

    for skill in skills:
        if not skill.enabled:
            continue

        skill_id = skill.id

        if skill_id == "web_search":
            try:
                from langchain_community.tools import DuckDuckGoSearchRun
                search = DuckDuckGoSearchRun()
                tools.append(
                    Tool(
                        name="busca_web",
                        func=search.run,
                        description=(
                            "Útil para buscar informações atualizadas na internet. "
                            "Use quando precisar de notícias recentes, fatos atuais ou informações que possam ter mudado. "
                            "Input: uma pergunta ou termo de busca em texto."
                        ),
                    )
                )
            except ImportError:
                tools.append(
                    Tool(
                        name="busca_web",
                        func=lambda q: "Erro: pacote duckduckgo-search não está instalado.",
                        description="Busca na web (indisponível - instale duckduckgo-search).",
                    )
                )

        elif skill_id == "code_execution":
            try:
                from langchain_community.tools.python.tool import PythonREPLTool
                repl = PythonREPLTool()
                tools.append(
                    Tool(
                        name="executar_codigo_python",
                        func=repl.run,
                        description=(
                            "Executa código Python e retorna o resultado. "
                            "Use para cálculos complexos, análise de dados, criação de scripts ou qualquer tarefa de programação. "
                            "Input: código Python válido como string."
                        ),
                    )
                )
            except ImportError:
                tools.append(
                    Tool(
                        name="executar_codigo_python",
                        func=lambda c: "Erro: ferramenta de execução de código indisponível.",
                        description="Executa código Python (indisponível).",
                    )
                )

        elif skill_id == "file_read":
            def read_file(path: str) -> str:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if len(content) > 10000:
                        content = content[:10000] + "\n... [arquivo truncado]"
                    return content
                except FileNotFoundError:
                    return f"Erro: arquivo '{path}' não encontrado."
                except PermissionError:
                    return f"Erro: sem permissão para ler '{path}'."
                except Exception as e:
                    return f"Erro ao ler arquivo: {str(e)}"

            tools.append(
                Tool(
                    name="ler_arquivo",
                    func=read_file,
                    description=(
                        "Lê o conteúdo de um arquivo de texto, CSV, JSON ou outro formato de texto. "
                        "Input: caminho completo para o arquivo (ex: /tmp/dados.csv)."
                    ),
                )
            )

        elif skill_id == "calculator":
            def calculate(expression: str) -> str:
                try:
                    # Safe evaluation of mathematical expressions
                    import math
                    allowed_names = {
                        k: v for k, v in math.__dict__.items() if not k.startswith("__")
                    }
                    allowed_names["abs"] = abs
                    allowed_names["round"] = round
                    result = eval(expression, {"__builtins__": {}}, allowed_names)
                    return str(result)
                except ZeroDivisionError:
                    return "Erro: divisão por zero."
                except Exception as e:
                    return f"Erro no cálculo: {str(e)}"

            tools.append(
                Tool(
                    name="calculadora",
                    func=calculate,
                    description=(
                        "Realiza operações matemáticas com precisão. "
                        "Suporta operações básicas (+, -, *, /), potências (**), raízes (sqrt), "
                        "logaritmos, trigonometria e mais. "
                        "Input: expressão matemática como string (ex: '2 + 2', 'sqrt(16)', '3 ** 2')."
                    ),
                )
            )

        elif skill_id == "datetime":
            def get_datetime(query: str = "") -> str:
                now = datetime.now(timezone.utc)
                from datetime import datetime as dt
                import locale
                return (
                    f"Data e hora atual (UTC): {now.strftime('%d/%m/%Y %H:%M:%S')}\n"
                    f"Dia da semana: {['Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'][now.weekday()]}\n"
                    f"Timestamp Unix: {int(now.timestamp())}"
                )

            tools.append(
                Tool(
                    name="data_hora_atual",
                    func=get_datetime,
                    description=(
                        "Retorna a data e hora atual em UTC. "
                        "Use quando o usuário perguntar que horas são, que dia é hoje, "
                        "ou precisar de informações sobre data e hora. "
                        "Input: qualquer string (ignorada)."
                    ),
                )
            )

        elif skill_id == "memory_recall":
            # Memory recall is handled at the memory config level
            # This tool provides an explicit recall interface
            def recall_memory(query: str) -> str:
                return (
                    "Memória de longo prazo: esta funcionalidade requer configuração de "
                    "banco de dados vetorial (ChromaDB ou similar) para persistência entre sessões."
                )

            tools.append(
                Tool(
                    name="lembrar_memoria",
                    func=recall_memory,
                    description=(
                        "Busca memórias de conversas anteriores. "
                        "Input: o que você quer lembrar ou buscar nas memórias anteriores."
                    ),
                )
            )

        elif skill_id == "email":
            cfg = skill.config or {}

            def send_email(input_str: str) -> str:
                import smtplib
                from email.mime.text import MIMEText
                import json

                try:
                    data = json.loads(input_str)
                    to_addr = data.get("to", "")
                    subject = data.get("subject", "Sem assunto")
                    body = data.get("body", "")
                except Exception:
                    return "Erro: input deve ser JSON com campos 'to', 'subject', 'body'."

                smtp_host = cfg.get("smtp_host", "smtp.gmail.com")
                smtp_port = int(cfg.get("smtp_port", 587))
                smtp_user = cfg.get("smtp_user", "")
                password_env = cfg.get("smtp_password_env", "EMAIL_PASSWORD")
                smtp_password = os.environ.get(password_env, "")

                if not smtp_user or not smtp_password:
                    return "Erro: credenciais de email não configuradas. Configure smtp_user e a variável de ambiente da senha."

                try:
                    msg = MIMEText(body, "plain", "utf-8")
                    msg["Subject"] = subject
                    msg["From"] = smtp_user
                    msg["To"] = to_addr

                    with smtplib.SMTP(smtp_host, smtp_port) as server:
                        server.starttls()
                        server.login(smtp_user, smtp_password)
                        server.sendmail(smtp_user, [to_addr], msg.as_string())

                    return f"Email enviado com sucesso para {to_addr}."
                except Exception as e:
                    return f"Erro ao enviar email: {str(e)}"

            tools.append(
                Tool(
                    name="enviar_email",
                    func=send_email,
                    description=(
                        "Envia um email. "
                        "Input: JSON com campos 'to' (destinatário), 'subject' (assunto), 'body' (corpo). "
                        'Exemplo: {"to": "pessoa@exemplo.com", "subject": "Olá", "body": "Mensagem aqui"}'
                    ),
                )
            )

    return tools


# ---------------------------------------------------------------------------
# Memory factory
# ---------------------------------------------------------------------------

def _build_memory(memory_cfg: MemoryConfig | None, llm: BaseChatModel) -> Any:
    if memory_cfg is None or memory_cfg.type == "none":
        return None

    if memory_cfg.type == "simple":
        return ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output",
        )

    elif memory_cfg.type == "semantic":
        return ConversationSummaryMemory(
            llm=llm,
            memory_key="chat_history",
            return_messages=True,
            output_key="output",
        )

    elif memory_cfg.type == "vector_rag":
        # Try to use ChromaDB for vector memory
        try:
            from langchain_community.vectorstores import Chroma
            try:
                from langchain_classic.memory import VectorStoreRetrieverMemory
            except ImportError:
                from langchain.memory import VectorStoreRetrieverMemory  # type: ignore

            # Use a simple in-memory chroma for now
            # In production this would be configured with a persistent path
            try:
                from langchain_openai import OpenAIEmbeddings
                embeddings = OpenAIEmbeddings(
                    api_key=os.environ.get("OPENAI_API_KEY", "sk-dummy")
                )
            except Exception:
                # Fallback to simple memory if embeddings fail
                return ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True,
                    output_key="output",
                )

            vectorstore = Chroma(
                collection_name="agent_memory",
                embedding_function=embeddings,
            )
            retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
            return VectorStoreRetrieverMemory(retriever=retriever)
        except Exception:
            # Fallback to simple memory
            return ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True,
                output_key="output",
            )

    # Default fallback
    return ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key="output",
    )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

REACT_PROMPT_TEMPLATE = """{system_prompt}

Você tem acesso às seguintes ferramentas:

{tools}

Use o seguinte formato OBRIGATÓRIO:

Question: a pergunta de entrada que você precisa responder
Thought: você deve sempre pensar sobre o que fazer
Action: a ação a ser tomada, deve ser uma de [{tool_names}]
Action Input: a entrada para a ação
Observation: o resultado da ação
... (este Thought/Action/Action Input/Observation pode se repetir N vezes)
Thought: agora eu sei a resposta final
Final Answer: a resposta final para a pergunta original do usuário

Histórico da conversa:
{chat_history}

Question: {input}
{agent_scratchpad}"""


def _build_prompt(config: AgentConfigSchema) -> PromptTemplate:
    persona = config.persona
    if persona:
        tone_instructions = {
            "friendly": "Seja sempre amigável, caloroso e acolhedor nas suas respostas.",
            "professional": "Mantenha um tom profissional, objetivo e formal.",
            "technical": "Use linguagem técnica precisa, mas explique termos complexos quando necessário.",
            "casual": "Use linguagem informal, descontraída e próxima do usuário.",
        }
        tone_text = tone_instructions.get(
            persona.tone,
            "Seja sempre prestativo e claro nas respostas."
        )

        system_prompt = (
            f"Você é {persona.name}. {persona.system_prompt}\n\n"
            f"{tone_text}\n"
            f"Responda sempre em português brasileiro, a menos que o usuário escreva em outro idioma."
        )
    else:
        system_prompt = (
            "Você é um assistente de IA prestativo. "
            "Responda sempre em português brasileiro, a menos que o usuário escreva em outro idioma."
        )

    return PromptTemplate.from_template(
        REACT_PROMPT_TEMPLATE.replace("{system_prompt}", system_prompt)
    )


# ---------------------------------------------------------------------------
# Main builder class
# ---------------------------------------------------------------------------

class AgentBuilder:
    """Builds a runnable LangChain AgentExecutor from an AgentConfigSchema."""

    def build(self, config: AgentConfigSchema) -> AgentExecutor:
        """
        Builds and returns a LangChain AgentExecutor.

        Raises:
            ValueError: If required config fields are missing.
            RuntimeError: If a required package is not installed.
        """
        if not config.model:
            raise ValueError(
                "Configuração de modelo não definida. "
                "Por favor, selecione um modelo de IA para o agente."
            )

        # Build the LLM
        llm = _build_llm(config.model)

        # Build tools from skills
        tools = _build_tools(config.skills)

        # Build memory
        memory = _build_memory(config.memory, llm)

        # Build prompt
        prompt = _build_prompt(config)

        # Build the React agent
        agent = create_react_agent(
            llm=llm,
            tools=tools,
            prompt=prompt,
        )

        # Build executor
        executor_kwargs: dict[str, Any] = {
            "agent": agent,
            "tools": tools,
            "verbose": True,
            "handle_parsing_errors": (
                "Desculpe, tive um problema ao processar a resposta. "
                "Por favor, tente reformular sua pergunta."
            ),
            "max_iterations": 10,
            "return_intermediate_steps": False,
        }

        if memory is not None:
            executor_kwargs["memory"] = memory

        executor = AgentExecutor(**executor_kwargs)
        return executor

    def build_simple_chain(self, config: AgentConfigSchema):
        """
        Builds a simple LLM chain without tools (fallback when no skills are configured).
        Returns a runnable chain.
        """
        try:
            from langchain_classic.chains import ConversationChain
            from langchain_classic.prompts import ChatPromptTemplate, MessagesPlaceholder
        except ImportError:
            from langchain.chains import ConversationChain  # type: ignore
            from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder  # type: ignore

        if not config.model:
            raise ValueError("Configuração de modelo não definida.")

        llm = _build_llm(config.model)
        memory = _build_memory(config.memory, llm)

        persona = config.persona
        if persona:
            system_content = (
                f"Você é {persona.name}. {persona.system_prompt}"
            )
        else:
            system_content = (
                "Você é um assistente de IA prestativo. "
                "Responda sempre em português brasileiro."
            )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_content),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}"),
        ])

        chain = ConversationChain(
            llm=llm,
            prompt=prompt,
            memory=memory or ConversationBufferMemory(return_messages=True),
            verbose=False,
        )
        return chain
