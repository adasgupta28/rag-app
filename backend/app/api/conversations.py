import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, delete, select

from app.api.deps import get_session
from app.db.models import Conversation, Message

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list[dict]
    rewritten_query: str | None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


@router.get("", response_model=list[ConversationOut])
def list_conversations(session: Session = Depends(get_session)) -> list[Conversation]:
    return list(session.exec(select(Conversation).order_by(Conversation.updated_at.desc())).all())


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, session: Session = Depends(get_session)) -> ConversationDetail:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    messages = session.exec(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    ).all()
    return ConversationDetail(
        **conversation.model_dump(),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=json.loads(m.sources_json) if m.sources_json else [],
                rewritten_query=m.rewritten_query,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, session: Session = Depends(get_session)) -> None:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    session.exec(delete(Message).where(Message.conversation_id == conversation_id))
    session.delete(conversation)
    session.commit()
