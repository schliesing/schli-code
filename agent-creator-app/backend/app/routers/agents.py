import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent import Agent
from app.schemas.agent import (
    AgentConfigSchema,
    AgentCreateRequest,
    AgentListItem,
    AgentUpdateRequest,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])


def _agent_to_config_schema(agent: Agent) -> AgentConfigSchema:
    """Convert ORM Agent to AgentConfigSchema."""
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


def _agent_to_list_item(agent: Agent) -> AgentListItem:
    """Convert ORM Agent to AgentListItem."""
    config = agent.config_json or {}
    framework = config.get("framework")
    characteristics = config.get("characteristics")
    persona = config.get("persona")

    return AgentListItem(
        id=agent.id,
        session_id=agent.session_id,
        name=agent.name,
        is_draft=agent.is_draft,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        current_step=config.get("current_step", 0),
        completed_steps=config.get("completed_steps", []),
        is_published=config.get("is_published", False),
        framework_id=framework.get("id") if framework else None,
        role=characteristics.get("role") if characteristics else None,
        avatar_emoji=persona.get("avatar_emoji") if persona else None,
    )


@router.post("", response_model=AgentConfigSchema, status_code=201)
def create_agent(body: AgentCreateRequest, db: Session = Depends(get_db)):
    """Cria um novo rascunho de agente para a sessão do usuário."""
    agent = Agent(
        id=str(uuid.uuid4()),
        session_id=body.user_session_id,
        name="Novo Agente",
        config_json={
            "current_step": 0,
            "completed_steps": [],
            "is_published": False,
            "skills": [],
        },
        is_draft=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _agent_to_config_schema(agent)


@router.get("", response_model=list[AgentListItem])
def list_agents(
    session_id: str = Query(..., description="ID da sessão do usuário"),
    db: Session = Depends(get_db),
):
    """Lista todos os agentes de uma sessão de usuário."""
    agents = (
        db.query(Agent)
        .filter(Agent.session_id == session_id)
        .order_by(Agent.updated_at.desc())
        .all()
    )
    return [_agent_to_list_item(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentConfigSchema)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Retorna a configuração completa de um agente."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    return _agent_to_config_schema(agent)


@router.patch("/{agent_id}", response_model=AgentConfigSchema)
def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    db: Session = Depends(get_db),
):
    """Atualiza parcialmente a configuração de um agente."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")

    config = dict(agent.config_json or {})
    update_data = body.model_dump(exclude_none=True)

    # Update top-level agent fields
    if "name" in update_data:
        agent.name = update_data.pop("name")
    if "is_draft" in update_data:
        agent.is_draft = update_data.pop("is_draft")

    # Update config_json fields
    for key, value in update_data.items():
        if value is not None:
            # Serialize nested Pydantic models to dicts
            if hasattr(value, "model_dump"):
                config[key] = value.model_dump()
            elif isinstance(value, list):
                config[key] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in value
                ]
            else:
                config[key] = value

    # Update persona name -> agent name sync
    if "persona" in config and isinstance(config["persona"], dict):
        persona_name = config["persona"].get("name")
        if persona_name:
            agent.name = persona_name

    agent.config_json = config
    agent.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(agent)
    return _agent_to_config_schema(agent)


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """Remove um agente permanentemente."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado.")
    db.delete(agent)
    db.commit()
