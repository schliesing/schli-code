"""
Export router: validates agent configs and serves .tar.gz download packages.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import Agent, AgentExport
from app.schemas.agent import AgentConfigSchema, ExportReadinessResponse
from app.services.exporter import AgentExporter

router = APIRouter(prefix="/api/export", tags=["export"])

EXPORT_TOKEN_TTL_HOURS = 24


def _load_config_from_agent(agent: Agent) -> AgentConfigSchema:
    """Construct AgentConfigSchema from ORM Agent."""
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


def _check_readiness(config: AgentConfigSchema) -> list[str]:
    """
    Returns a list of missing required fields.
    An empty list means the config is complete and ready to export.
    """
    missing: list[str] = []

    if not config.framework:
        missing.append("framework")

    if not config.characteristics:
        missing.append("characteristics (papel do agente)")

    if not config.model:
        missing.append("model (modelo de IA)")
    else:
        if not config.model.provider:
            missing.append("model.provider")
        if not config.model.model_id:
            missing.append("model.model_id")

    if not config.persona:
        missing.append("persona (identidade do agente)")
    else:
        if not config.persona.name:
            missing.append("persona.name")
        if not config.persona.system_prompt:
            missing.append("persona.system_prompt")
        if not config.persona.greeting:
            missing.append("persona.greeting")

    if not config.memory:
        missing.append("memory (configuração de memória)")

    if not config.deployment:
        missing.append("deployment (destino de deploy)")
    elif not config.deployment.targets:
        missing.append("deployment.targets (pelo menos um destino de deploy)")

    return missing


@router.post("/prepare", response_model=ExportReadinessResponse)
def prepare_export(
    body: dict,
    db: Session = Depends(get_db),
):
    """
    Validates that an agent configuration is complete and ready for export.
    Returns {ready: bool, missing: list[str]}.
    """
    agent_id = body.get("agent_id", "")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id é obrigatório.")

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")

    config = _load_config_from_agent(agent)
    missing = _check_readiness(config)

    return ExportReadinessResponse(ready=len(missing) == 0, missing=missing)


@router.get("/{download_token}")
def download_export(download_token: str, db: Session = Depends(get_db)):
    """
    Streams the agent .tar.gz package.
    - Validates the download token
    - Token is single-use
    - Token expires after 24 hours
    """
    now = datetime.now(timezone.utc)

    export_record = (
        db.query(AgentExport)
        .filter(AgentExport.download_token == download_token)
        .first()
    )

    if not export_record:
        raise HTTPException(
            status_code=404,
            detail="Token de download não encontrado. Verifique o link e tente novamente.",
        )

    if export_record.downloaded_at is not None:
        raise HTTPException(
            status_code=410,
            detail=(
                "Este link de download já foi utilizado. "
                "Links de download são válidos para um único uso. "
                "Realize um novo pagamento para obter um novo link."
            ),
        )

    # Check expiry - handle timezone-aware vs naive comparison
    expires_at = export_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if now > expires_at:
        raise HTTPException(
            status_code=410,
            detail=(
                "Este link de download expirou. "
                f"Os links expiram em {EXPORT_TOKEN_TTL_HOURS} horas após o pagamento."
            ),
        )

    # Load agent
    agent = db.query(Agent).filter(Agent.id == export_record.agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agente associado a este download não foi encontrado.",
        )

    config = _load_config_from_agent(agent)
    missing = _check_readiness(config)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Configuração do agente incompleta. Campos faltando: {', '.join(missing)}",
        )

    # Mark as downloaded (single-use)
    export_record.downloaded_at = now
    db.commit()

    # Generate the package
    exporter = AgentExporter()
    tar_buffer = exporter.export(config)
    filename = exporter.get_filename(config)

    def iter_file():
        chunk_size = 64 * 1024  # 64KB chunks
        while True:
            chunk = tar_buffer.read(chunk_size)
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Agent-Name": config.persona.name if config.persona else "Agente",
        },
    )


@router.post("/create-token/{agent_id}", include_in_schema=False)
def create_download_token(
    agent_id: str,
    payment_id: str | None = None,
    db: Session = Depends(get_db),
):
    """
    Internal endpoint to create a download token (called by payment webhook).
    Not exposed in public API docs.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=EXPORT_TOKEN_TTL_HOURS)

    export_record = AgentExport(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        payment_id=payment_id,
        download_token=token,
        expires_at=expires_at,
    )
    db.add(export_record)
    db.commit()
    db.refresh(export_record)

    return {
        "download_token": token,
        "expires_at": expires_at.isoformat(),
        "download_url": f"/api/export/{token}",
    }
