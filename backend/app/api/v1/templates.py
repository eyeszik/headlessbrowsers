"""Template management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from backend.app.db.session import get_session
from backend.app.models.models import ContentTemplate
from backend.app.crud.crud import crud_content_template
from backend.app.services.template_engine import template_engine

router = APIRouter()


@router.get("/", response_model=List[ContentTemplate])
def list_templates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_session)
):
    """List all templates."""
    return crud_content_template.get_multi(db, skip=skip, limit=limit)


@router.post("/", response_model=ContentTemplate)
def create_template(
    template_data: dict,
    db: Session = Depends(get_session)
):
    """Create new template."""
    # Validate template
    validation = template_engine.validate_template(
        template_data.get("template_text", "")
    )
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid template: {validation['errors']}"
        )

    return crud_content_template.create(db, template_data)


@router.post("/preview")
def preview_template(
    template_text: str,
    variables: dict
):
    """Preview template with sample data."""
    result = template_engine.preview_template(template_text, variables)
    return result
