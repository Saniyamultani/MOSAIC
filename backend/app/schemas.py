from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TextIngestRequest(BaseModel):
    text: str = Field(min_length=1)
    kind_hint: str | None = None
    title: str | None = None


class UrlIngestRequest(BaseModel):
    url: str
    kind_hint: str | None = None


class ConfirmRequest(BaseModel):
    thread_id: str | None = None
    overrides: dict[str, Any] = Field(default_factory=dict)


class AssistantRequest(BaseModel):
    question: str | None = None
    message: str | None = None
    conversation_id: str | None = None

    def get_message(self) -> str:
        return (self.message or self.question or "").strip()


class AssistantChatRequest(BaseModel):
    message: str | None = None
    question: str | None = None
    conversation_id: str | None = None

    def get_message(self) -> str:
        return (self.message or self.question or "").strip()


class PublishRequest(BaseModel):
    source_name: str = "Manual injection"
    title: str
    body: str = ""
    category: str = "external_update"
    url: str | None = None
    trust_tier: int = 2
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentOut(BaseModel):
    id: str
    kind: str
    title: str
    status: str
    filename: str | None = None
    source_url: str | None = None
    extraction: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class IngestResponse(BaseModel):
    document: DocumentOut
    thread_id: str
    trace: list[dict[str, Any]]
    awaiting_confirmation: bool = True


class ProfileField(BaseModel):
    """A single editable profile field with user-controlled sharing."""
    value: Any = None
    shared: bool = True


class ProfileUpdateRequest(BaseModel):
    """Partial-patch body for PUT /api/profile.

    Each key is a field name; each value is a ProfileField.
    Missing keys are left unchanged (partial update semantics).
    """
    display_name: ProfileField | None = None
    city: ProfileField | None = None
    country: ProfileField | None = None
    age: ProfileField | None = None
    language: ProfileField | None = None
    currency: ProfileField | None = None
    interests: ProfileField | None = None
    notification_style: ProfileField | None = None
    # Catch-all for arbitrary extra fields
    extra: dict[str, ProfileField] = Field(default_factory=dict)
