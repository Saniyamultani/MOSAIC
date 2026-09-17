"""Profile API — GET and PUT /api/profile.

Stores user profile as a JSON blob on the User row (no separate table).
Each field is a {"value": ..., "shared": bool} dict.
Only shared=True fields are visible to the Assistant.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..schemas import ProfileUpdateRequest
from .deps import current_user

router = APIRouter(prefix="/api", tags=["profile"])

# Fields that appear in the profile (ordered for UI display)
PROFILE_FIELDS = [
    "display_name",
    "city",
    "country",
    "age",
    "language",
    "currency",
    "interests",
    "notification_style",
]

# Default values for each field (used when first initialising)
FIELD_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "display_name": {"value": None, "shared": True},
    "city":         {"value": None, "shared": True},
    "country":      {"value": "India", "shared": True},
    "age":          {"value": None, "shared": False},
    "language":     {"value": "English", "shared": True},
    "currency":     {"value": "INR", "shared": True},
    "interests":    {"value": [], "shared": True},
    "notification_style": {"value": "concise", "shared": False},
}


def _get_profile(user: User) -> Dict[str, Any]:
    """Return the full profile dict, filling in defaults for missing fields."""
    stored: Dict[str, Any] = user.profile_json or {}
    profile: Dict[str, Any] = {}
    for field in PROFILE_FIELDS:
        profile[field] = stored.get(field, dict(FIELD_DEFAULTS[field]))
    # Include any extra fields the user may have added
    for key, val in stored.items():
        if key not in profile:
            profile[key] = val
    return profile


@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Dict[str, Any]:
    """Return the current user's full profile."""
    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "profile": _get_profile(user),
    }


@router.put("/profile")
def update_profile(
    body: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> Dict[str, Any]:
    """Partial-patch the user's profile.

    Only keys present in the request body are updated.
    Omitted keys are left unchanged (partial-update semantics).
    """
    stored: Dict[str, Any] = dict(user.profile_json or {})

    # Update named fields
    known_fields = [
        "display_name", "city", "country", "age",
        "language", "currency", "interests", "notification_style",
    ]
    for field in known_fields:
        field_val = getattr(body, field, None)
        if field_val is not None:
            stored[field] = {"value": field_val.value, "shared": field_val.shared}

    # Update any extra fields
    for key, field_val in (body.extra or {}).items():
        stored[key] = {"value": field_val.value, "shared": field_val.shared}

    # Sync display_name → user.name if provided and shared
    if "display_name" in stored and stored["display_name"].get("value"):
        user.name = stored["display_name"]["value"]

    # SQLAlchemy JSON column needs explicit assignment to detect mutation
    user.profile_json = stored
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "profile": _get_profile(user),
    }


def build_profile_context(user: User) -> str:
    """Build a context string for the Assistant from the user's shared profile fields.

    Only fields where ``shared=True`` are included.
    Returns an empty string if the profile is empty or all fields are unshared.
    """
    profile = _get_profile(user)
    lines = []
    field_labels = {
        "display_name": "Name",
        "city": "City",
        "country": "Country",
        "age": "Age",
        "language": "Preferred language",
        "currency": "Currency",
        "interests": "Interests",
        "notification_style": "Notification style",
    }
    for field, data in profile.items():
        if not data.get("shared", False):
            continue
        val = data.get("value")
        if val is None or val == "" or val == []:
            continue
        label = field_labels.get(field, field.replace("_", " ").title())
        display_val = ", ".join(val) if isinstance(val, list) else str(val)
        lines.append(f"  {label}: {display_val}")

    if not lines:
        return ""

    return "USER PROFILE CONTEXT (shared preferences — always honour these):\n" + "\n".join(lines)
