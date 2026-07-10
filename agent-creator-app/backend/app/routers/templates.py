from fastapi import APIRouter, HTTPException
from app.data.templates import TEMPLATES, TEMPLATE_INDEX

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
def list_templates():
    """Retorna a lista de templates disponíveis com informações resumidas."""
    summary = [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "icon_emoji": t["icon_emoji"],
            "tags": t["tags"],
            "complexity": t["complexity"],
        }
        for t in TEMPLATES
    ]
    return {"templates": summary}


@router.get("/{template_id}")
def get_template(template_id: str):
    """Retorna o template completo com a configuração do agente."""
    template = TEMPLATE_INDEX.get(template_id)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Template '{template_id}' não encontrado.",
        )
    return template
