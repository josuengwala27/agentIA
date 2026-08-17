from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.services.accounts import normalize_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == normalize_email(form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.organization_id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login/json", response_model=TokenResponse)
def login_json(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == normalize_email(payload.email)).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.organization_id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: dict, db: Session = Depends(get_db)):
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token requis")
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token refresh invalide")
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return TokenResponse(
        access_token=create_access_token(user.id, user.role, user.organization_id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
