from fastapi import APIRouter
from app.data.catalog import (
    FRAMEWORKS,
    AGENT_ROLES,
    SKILLS,
    MODELS,
    MEMORY_TYPES,
    DEPLOYMENT_TARGETS,
)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/frameworks")
def get_frameworks():
    """Retorna a lista de frameworks disponíveis para criar agentes."""
    return {"frameworks": FRAMEWORKS}


@router.get("/skills")
def get_skills():
    """Retorna a lista de habilidades que podem ser adicionadas ao agente."""
    return {"skills": SKILLS}


@router.get("/models")
def get_models():
    """Retorna a lista de modelos de IA disponíveis, agrupados por provedor."""
    providers: dict[str, list] = {}
    for model in MODELS:
        provider = model["provider"]
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(model)

    return {
        "models": MODELS,
        "by_provider": providers,
    }


@router.get("/memory-types")
def get_memory_types():
    """Retorna os tipos de memória disponíveis para o agente."""
    return {"memory_types": MEMORY_TYPES}


@router.get("/deployment-targets")
def get_deployment_targets():
    """Retorna os destinos de deploy disponíveis para o agente."""
    return {"deployment_targets": DEPLOYMENT_TARGETS}


@router.get("/roles")
def get_roles():
    """Retorna os papéis (roles) disponíveis para o agente."""
    return {"roles": AGENT_ROLES}
