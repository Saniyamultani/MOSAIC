"""Authentication API — signup, login, logout, and current user me query."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..services import (
    create_user_session,
    delete_user_session,
    hash_password,
    verify_password,
)
from .deps import current_user, extract_token
from .profile import _get_profile

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=3, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/signup")
def signup(body: SignupRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    email = body.email.strip().lower()
    name = body.name.strip()
    password = body.password

    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=email,
        name=name,
        hashed_password=hash_password(password),
        profile_json={
            "display_name": {"value": name, "shared": True},
            "country": {"value": "India", "shared": True},
            "currency": {"value": "INR", "shared": True},
            "language": {"value": "English", "shared": True},
        },
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_user_session(db, user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "profile": _get_profile(user),
        },
    }


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    email = body.email.strip().lower()
    password = body.password

    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_user_session(db, user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "profile": _get_profile(user),
        },
    }


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    token = extract_token(request)
    if token:
        delete_user_session(db, token)
    return {"status": "logged_out"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> Dict[str, Any]:
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "profile": _get_profile(user),
        }
    }
