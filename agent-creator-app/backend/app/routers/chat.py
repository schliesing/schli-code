"""
WebSocket endpoint for testing agents in real-time.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.agent import Agent
from app.schemas.agent import AgentConfigSchema
from app.services.agent_builder import AgentBuilder

router = APIRouter(tags=["chat"])


def _load_agent_config(agent_id: str, session_id: str) -> AgentConfigSchema | None:
    """Load agent config from DB, verify session ownership."""
    db: Session = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return None
        if agent.session_id != session_id:
            return None

        config = agent.config_json or {}
        return AgentConfigSchema(
            id=agent.id,
            user_session_id=agent.session_id,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
            framework=config.get("framework"),
            characteristics=config.get("characteristics"),
            skills=config.get("skills", []),
            model=config.get("model"),
            memory=config.get("memory"),
            persona=config.get("persona"),
            deployment=config.get("deployment"),
            current_step=config.get("current_step", 0),
            completed_steps=config.get("completed_steps", []),
            is_published=config.get("is_published", False),
        )
    finally:
        db.close()


async def _send_json(ws: WebSocket, data: dict) -> None:
    """Send a JSON message to the WebSocket client."""
    await ws.send_text(json.dumps(data, ensure_ascii=False))


async def _stream_agent_response(
    ws: WebSocket,
    executor: Any,
    user_message: str,
) -> None:
    """
    Run the agent and stream tokens back to the WebSocket client.
    Uses astream_events for token-level streaming.
    """
    full_response = ""
    try:
        async for event in executor.astream_events(
            {"input": user_message},
            version="v1",
        ):
            kind = event.get("event", "")

            if kind == "on_llm_stream":
                chunk = event.get("data", {}).get("chunk", "")
                if hasattr(chunk, "content"):
                    token = chunk.content
                elif isinstance(chunk, str):
                    token = chunk
                else:
                    token = str(chunk)

                if token:
                    full_response += token
                    await _send_json(ws, {"type": "token", "content": token})

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content
                    await _send_json(ws, {"type": "token", "content": chunk.content})

    except Exception as stream_err:
        # If streaming fails, try synchronous invocation
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: executor.invoke({"input": user_message}),
            )
            output = result.get("output", str(result))
            # Send as single token for compatibility
            await _send_json(ws, {"type": "token", "content": output})
            full_response = output
        except Exception as invoke_err:
            await _send_json(
                ws,
                {"type": "error", "content": f"Erro ao processar mensagem: {str(invoke_err)}"},
            )
            return

    await _send_json(ws, {"type": "done", "content": ""})


@router.websocket("/ws/chat/{agent_id}")
async def websocket_chat(websocket: WebSocket, agent_id: str):
    """
    WebSocket endpoint for real-time agent testing.

    Protocol:
        Client -> Server: {"type": "message", "content": "...", "session_id": "..."}
        Client -> Server: {"type": "reset"}
        Server -> Client: {"type": "token", "content": "H"}    (streaming token)
        Server -> Client: {"type": "done", "content": ""}       (response complete)
        Server -> Client: {"type": "error", "content": "..."}   (error message)
    """
    await websocket.accept()

    executor = None
    current_session_id: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send_json(
                    websocket,
                    {"type": "error", "content": "Mensagem inválida: JSON malformado."},
                )
                continue

            msg_type = data.get("type", "message")

            if msg_type == "reset":
                # Reset conversation: rebuild executor
                executor = None
                await _send_json(websocket, {"type": "done", "content": ""})
                continue

            if msg_type != "message":
                await _send_json(
                    websocket,
                    {"type": "error", "content": f"Tipo de mensagem desconhecido: {msg_type}"},
                )
                continue

            session_id = data.get("session_id", "")
            user_content = data.get("content", "").strip()

            if not user_content:
                await _send_json(
                    websocket,
                    {"type": "error", "content": "Mensagem vazia. Por favor, escreva algo."},
                )
                continue

            if not session_id:
                await _send_json(
                    websocket,
                    {"type": "error", "content": "session_id é obrigatório."},
                )
                continue

            # Build or reuse executor
            if executor is None or current_session_id != session_id:
                config = _load_agent_config(agent_id, session_id)
                if config is None:
                    await _send_json(
                        websocket,
                        {
                            "type": "error",
                            "content": (
                                "Agente não encontrado ou você não tem permissão para acessá-lo. "
                                "Verifique o agent_id e session_id."
                            ),
                        },
                    )
                    continue

                if not config.model:
                    await _send_json(
                        websocket,
                        {
                            "type": "error",
                            "content": (
                                "Este agente ainda não tem um modelo configurado. "
                                "Por favor, complete a configuração do modelo antes de testar."
                            ),
                        },
                    )
                    continue

                try:
                    builder = AgentBuilder()
                    executor = builder.build(config)
                    current_session_id = session_id
                except Exception as build_err:
                    await _send_json(
                        websocket,
                        {
                            "type": "error",
                            "content": (
                                f"Erro ao inicializar o agente: {str(build_err)}\n\n"
                                "Verifique se as chaves de API estão configuradas corretamente."
                            ),
                        },
                    )
                    continue

            # Stream the agent response
            await _stream_agent_response(websocket, executor, user_content)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await _send_json(
                websocket,
                {"type": "error", "content": f"Erro interno: {str(e)}"},
            )
        except Exception:
            pass
