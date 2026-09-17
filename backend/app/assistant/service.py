"""Assistant service orchestrating conversation persistence, chat management, and LangGraph execution."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..llm.factory import get_llm
from ..models import Conversation, ConversationMessage, User, utcnow
from .graph import assistant_graph


def run_assistant_chat(
    db: Session,
    user_id: str,
    message: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute conversational LangGraph assistant flow with DB persistence and user isolation."""
    clean_message = message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    conversation = None
    if conversation_id:
        conversation = db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        ).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # Title conversation after first message query snippet
        title_snippet = clean_message[:40] if clean_message else "MOSAIC Assistant"
        conversation = Conversation(user_id=user_id, title=title_snippet)
        db.add(conversation)
        db.flush()

    # Load recent conversation history (last 12 messages)
    previous_messages = list(
        db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(12)
        ).scalars()
    )[::-1]

    history = [{"role": msg.role, "content": msg.content} for msg in previous_messages]

    # Save user message to database
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=clean_message,
        )
    )
    db.flush()

    # Run LangGraph workflow
    initial_state = {
        "db": db,
        "user_id": user_id,
        "conversation_id": conversation.id,
        "question": clean_message,
        "history": history,
    }

    final_state = assistant_graph.invoke(initial_state)

    answer = final_state.get("answer", "Hello! How can I help you today?")
    entities = final_state.get("entities", [])
    sources = final_state.get("sources", [])
    evidence = final_state.get("evidence", [])

    # Save assistant answer to database
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
        )
    )

    conversation.updated_at = utcnow()
    db.commit()

    return {
        "conversation_id": conversation.id,
        "message": clean_message,
        "answer": answer,
        "entities": entities,
        "sources": sources,
        "evidence": evidence,
        "provider": get_llm().name,
    }


def list_user_chats(db: Session, user_id: str) -> List[Dict[str, Any]]:
    """List all assistant conversations for the current user."""
    conversations = list(
        db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        ).scalars()
    )

    out: List[Dict[str, Any]] = []
    for conv in conversations:
        last_msg = db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        msg_count = db.scalar(
            select(func.count(ConversationMessage.id)).where(
                ConversationMessage.conversation_id == conv.id
            )
        ) or 0

        out.append({
            "id": conv.id,
            "title": conv.title or "MOSAIC Chat",
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "message_count": msg_count,
            "last_message": last_msg.content if last_msg else None,
        })
    return out


def get_chat_history(db: Session, user_id: str, conversation_id: str) -> Dict[str, Any]:
    """Get full message history for a specific user conversation."""
    conversation = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = list(
        db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation.id)
            .order_by(ConversationMessage.created_at.asc())
        ).scalars()
    )

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


def delete_user_chat(db: Session, user_id: str, conversation_id: str) -> Dict[str, Any]:
    """Delete a user conversation. Crucially preserves all Life Graph/Entity/Document data."""
    conversation = db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()

    return {"status": "deleted", "id": conversation_id}
