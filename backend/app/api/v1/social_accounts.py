"""Social account management endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from backend.app.db.session import get_session
from backend.app.models.models import SocialAccount
from backend.app.crud.crud import crud_social_account

router = APIRouter()


@router.get("/", response_model=List[SocialAccount])
def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_session)
):
    """List all social accounts."""
    return crud_social_account.get_multi(db, skip=skip, limit=limit)


@router.get("/{account_id}", response_model=SocialAccount)
def get_account(
    account_id: int,
    db: Session = Depends(get_session)
):
    """Get specific account."""
    account = crud_social_account.get(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("/", response_model=SocialAccount)
def create_account(
    account_data: dict,
    db: Session = Depends(get_session)
):
    """Create new social account."""
    return crud_social_account.create(db, account_data)
