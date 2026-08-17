from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_roles
from app.core.security import hash_password
from app.db.session import get_db
from app.models import User, UserRole
from app.schemas import (
    CreateUserRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SetActiveRequest,
    UserAdminOut,
    UserCreatedOut,
)
from app.services.accounts import (
    generate_temporary_password,
    normalize_email,
    validate_role,
)

router = APIRouter(prefix="/users", tags=["users"])


def _admin(user: User = Depends(require_roles(UserRole.ADMIN))) -> User:
    return user


def _in_org(db: Session, admin: User, user_id: str) -> User:
    target = (
        db.query(User)
        .filter(User.id == user_id, User.organization_id == admin.organization_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    return target


def _active_admin_count(db: Session, organization_id: str, exclude_id: str | None = None) -> int:
    q = db.query(User).filter(
        User.organization_id == organization_id,
        User.role == UserRole.ADMIN.value,
        User.is_active.is_(True),
    )
    if exclude_id:
        q = q.filter(User.id != exclude_id)
    return q.count()


@router.get("", response_model=list[UserAdminOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(_admin)):
    return (
        db.query(User)
        .filter(User.organization_id == admin.organization_id)
        .order_by(User.created_at.asc())
        .all()
    )


@router.post("", response_model=UserCreatedOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_admin),
):
    try:
        role = validate_role(payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    email = normalize_email(payload.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Cet email est déjà utilisé")
    temporary = None
    password = payload.password
    if not password:
        temporary = generate_temporary_password()
        password = temporary
    user = User(
        organization_id=admin.organization_id,
        email=email,
        full_name=payload.full_name.strip(),
        role=role,
        hashed_password=hash_password(password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    data = UserCreatedOut.model_validate(user)
    data.temporary_password = temporary
    return data


@router.patch("/{user_id}/active", response_model=UserAdminOut)
def set_active(
    user_id: str,
    payload: SetActiveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_admin),
):
    target = _in_org(db, admin, user_id)
    if target.id == admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")
    if (
        not payload.is_active
        and target.role == UserRole.ADMIN.value
        and _active_admin_count(db, admin.organization_id, exclude_id=target.id) == 0
    ):
        raise HTTPException(status_code=400, detail="Impossible de désactiver le dernier administrateur")
    target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    user_id: str,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_admin),
):
    target = _in_org(db, admin, user_id)
    temporary = payload.password or generate_temporary_password()
    target.hashed_password = hash_password(temporary)
    db.commit()
    return ResetPasswordResponse(temporary_password=temporary)
