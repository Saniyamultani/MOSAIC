from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..assistant.service import (
    delete_user_chat,
    get_chat_history,
    list_user_chats,
    run_assistant_chat,
)
from ..db import get_db
from ..models import User
from ..schemas import AssistantChatRequest, AssistantRequest
from .deps import current_user

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("")
def ask(
    body: AssistantRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    msg = body.get_message()
    return run_assistant_chat(
        db=db,
        user_id=user.id,
        message=msg,
        conversation_id=body.conversation_id,
    )


@router.post("/chat")
def chat(
    body: AssistantChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    msg = body.get_message()
    return run_assistant_chat(
        db=db,
        user_id=user.id,
        message=msg,
        conversation_id=body.conversation_id,
    )


@router.get("/chats")
def list_chats(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return {"chats": list_user_chats(db=db, user_id=user.id)}


@router.get("/chats/{conversation_id}")
def get_chat(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return get_chat_history(db=db, user_id=user.id, conversation_id=conversation_id)


@router.delete("/chats/{conversation_id}")
def delete_chat(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return delete_user_chat(db=db, user_id=user.id, conversation_id=conversation_id)
