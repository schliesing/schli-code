"""
AgentExporter: Generates in-memory .tar.gz packages from agent configurations.
Uses Jinja2 templates to render all necessary files.
"""
from __future__ import annotations

import io
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.agent import AgentConfigSchema

# Path to Jinja2 templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _get_jinja_env() -> Environment:
    """Create and configure the Jinja2 environment."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )

    # Custom filter to convert Python objects to JSON strings in templates
    import json

    env.filters["tojson"] = lambda v: json.dumps(v, ensure_ascii=False)

    return env


def _config_to_template_context(config: AgentConfigSchema) -> dict[str, Any]:
    """Convert AgentConfigSchema to a flat dict for template rendering."""
    ctx: dict[str, Any] = {}

    ctx["framework"] = config.framework.model_dump() if config.framework else None
    ctx["characteristics"] = config.characteristics.model_dump() if config.characteristics else None
    ctx["skills"] = [s.model_dump() for s in config.skills]
    ctx["model"] = config.model.model_dump() if config.model else None
    ctx["memory"] = config.memory.model_dump() if config.memory else None
    ctx["persona"] = config.persona.model_dump() if config.persona else None
    ctx["deployment"] = config.deployment.model_dump() if config.deployment else None
    ctx["current_step"] = config.current_step
    ctx["is_published"] = config.is_published
    ctx["agent_id"] = config.id or "unknown"

    # Add helper booleans for deployment targets
    targets = []
    if config.deployment:
        targets = config.deployment.targets or []
    ctx["has_telegram"] = "telegram" in targets
    ctx["has_discord"] = "discord" in targets
    ctx["has_rest_api"] = "rest_api" in targets
    ctx["has_web_widget"] = "web_widget" in targets
    ctx["has_whatsapp"] = "whatsapp" in targets

    return ctx


def _render_template(env: Environment, template_name: str, context: dict) -> str:
    """Render a Jinja2 template with the given context."""
    template = env.get_template(template_name)
    return template.render(**context)


def _add_file_to_tar(
    tar: tarfile.TarFile,
    name: str,
    content: str,
    mode: int = 0o644,
) -> None:
    """Add a string content as a file to the tarball."""
    encoded = content.encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(encoded)
    info.mode = mode
    info.mtime = int(datetime.now(timezone.utc).timestamp())
    tar.addfile(info, io.BytesIO(encoded))


class AgentExporter:
    """Generates a .tar.gz package from an AgentConfigSchema."""

    def export(self, config: AgentConfigSchema) -> io.BytesIO:
        """
        Generate a complete .tar.gz package for the agent.

        Returns:
            BytesIO object containing the .tar.gz data, ready to stream/send.
        """
        env = _get_jinja_env()
        ctx = _config_to_template_context(config)

        # Determine agent folder name
        agent_name = "agente"
        if config.persona and config.persona.name:
            # Sanitize name for filesystem
            agent_name = (
                config.persona.name.lower()
                .replace(" ", "-")
                .replace("/", "-")
                .replace("\\", "-")
                [:32]
            )
        elif config.id:
            agent_name = f"agente-{config.id[:8]}"

        prefix = agent_name

        buffer = io.BytesIO()

        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            # main.py
            main_content = _render_template(env, "agent_main.py.j2", ctx)
            _add_file_to_tar(tar, f"{prefix}/main.py", main_content, mode=0o755)

            # agent_definition.py
            agent_def_content = _render_template(env, "agent_definition.py.j2", ctx)
            _add_file_to_tar(tar, f"{prefix}/agent_definition.py", agent_def_content)

            # requirements.txt
            requirements_content = _render_template(env, "requirements.txt.j2", ctx)
            _add_file_to_tar(tar, f"{prefix}/requirements.txt", requirements_content)

            # Dockerfile
            dockerfile_content = _render_template(env, "Dockerfile.j2", ctx)
            _add_file_to_tar(tar, f"{prefix}/Dockerfile", dockerfile_content)

            # docker-compose.yml
            docker_compose_content = _render_template(env, "docker-compose.yml.j2", ctx)
            _add_file_to_tar(tar, f"{prefix}/docker-compose.yml", docker_compose_content)

            # .env.example
            env_example_content = _render_template(env, ".env.example.j2", ctx)
            _add_file_to_tar(tar, f"{prefix}/.env.example", env_example_content)

            # README.md
            readme_content = _render_template(env, "README.md.j2", ctx)
            _add_file_to_tar(tar, f"{prefix}/README.md", readme_content)

            # Deployment-specific files
            targets = []
            if config.deployment:
                targets = config.deployment.targets or []

            if "telegram" in targets:
                telegram_content = _render_template(env, "telegram_bot.py.j2", ctx)
                _add_file_to_tar(tar, f"{prefix}/telegram_bot.py", telegram_content)

            if "rest_api" in targets or "web_widget" in targets or "whatsapp" in targets:
                rest_api_content = _render_template(env, "rest_api.py.j2", ctx)
                _add_file_to_tar(tar, f"{prefix}/rest_api.py", rest_api_content)

            if "web_widget" in targets:
                widget_content = _render_template(env, "web_widget/index.html.j2", ctx)
                _add_file_to_tar(tar, f"{prefix}/web_widget/index.html", widget_content)

            if "discord" in targets:
                discord_content = _generate_discord_bot(ctx)
                _add_file_to_tar(tar, f"{prefix}/discord_bot.py", discord_content)

            if "whatsapp" in targets:
                whatsapp_content = _generate_whatsapp_handler(ctx)
                _add_file_to_tar(tar, f"{prefix}/whatsapp_handler.py", whatsapp_content)

        buffer.seek(0)
        return buffer

    def get_filename(self, config: AgentConfigSchema) -> str:
        """Return a sanitized filename for the .tar.gz download."""
        agent_name = "agente"
        if config.persona and config.persona.name:
            agent_name = (
                config.persona.name.lower()
                .replace(" ", "-")
                .replace("/", "-")
                .replace("\\", "-")
                [:24]
            )
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"{agent_name}-{timestamp}.tar.gz"


def _generate_discord_bot(ctx: dict) -> str:
    """Generate Discord bot code."""
    persona = ctx.get("persona") or {}
    deployment = ctx.get("deployment") or {}
    discord_config = deployment.get("discord_config", {}) if deployment else {}

    name = persona.get("name", "Agente IA")
    greeting = persona.get("greeting", "Olá!")
    emoji = persona.get("avatar_emoji", "🤖")
    command_prefix = discord_config.get("command_prefix", "!")

    return f'''"""
{name} - Bot do Discord
Gerado automaticamente pelo Agent Creator App
"""

import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from agent_definition import create_agent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="{command_prefix}", intents=intents)
agent = create_agent()


@bot.event
async def on_ready():
    logger.info(f"Bot {{bot.user}} está online!")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="suas mensagens"
        )
    )


@bot.command(name="inicio", aliases=["start", "ola"])
async def start_command(ctx):
    await ctx.send("{greeting}")


@bot.command(name="ajuda", aliases=["help"])
async def help_command(ctx):
    embed = discord.Embed(
        title="{name} {emoji}",
        description="{greeting}",
        color=discord.Color.purple(),
    )
    embed.add_field(name="{command_prefix}inicio", value="Inicia a conversa", inline=False)
    embed.add_field(name="{command_prefix}ajuda", value="Mostra esta mensagem", inline=False)
    embed.set_footer(text="Gerado por Agent Creator App")
    await ctx.send(embed=embed)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    # Responde a menções
    if bot.user in message.mentions:
        user_text = message.content.replace(f"<@{{bot.user.id}}>", "").strip()
        if not user_text:
            await message.channel.send("{greeting}")
            return

        async with message.channel.typing():
            try:
                result = agent.invoke({{"input": user_text}})
                response = result.get("output", str(result))
                if len(response) > 2000:
                    for i in range(0, len(response), 2000):
                        await message.channel.send(response[i:i+2000])
                else:
                    await message.channel.send(response)
            except Exception as e:
                logger.error(f"Erro: {{e}}")
                await message.channel.send("Desculpe, tive um problema ao processar sua mensagem.")


def run_discord_bot():
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN não configurado no arquivo .env")
    bot.run(token)


if __name__ == "__main__":
    run_discord_bot()
'''


def _generate_whatsapp_handler(ctx: dict) -> str:
    """Generate WhatsApp webhook handler via Twilio."""
    persona = ctx.get("persona") or {}
    name = persona.get("name", "Agente IA")
    greeting = persona.get("greeting", "Olá!")

    return f'''"""
{name} - Handler WhatsApp via Twilio
Gerado automaticamente pelo Agent Creator App
"""

import os
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from agent_definition import create_agent

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="{name} WhatsApp")
agent = create_agent()


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    Body: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
):
    """Processa mensagens do WhatsApp via Twilio webhook."""
    user_message = Body.strip()
    logger.info(f"Mensagem de {{From}}: {{user_message}}")

    try:
        if user_message.lower() in ("oi", "olá", "ola", "start", "inicio"):
            reply = "{greeting}"
        else:
            result = agent.invoke({{"input": user_message}})
            reply = result.get("output", str(result))
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {{e}}")
        reply = "Desculpe, tive um problema ao processar sua mensagem. Tente novamente."

    # Limita para 1600 chars (limite do WhatsApp)
    if len(reply) > 1600:
        reply = reply[:1597] + "..."

    resp = MessagingResponse()
    resp.message(reply)
    return Response(content=str(resp), media_type="application/xml")


@app.get("/health")
async def health():
    return {{"status": "ok", "agent": "{name}"}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
