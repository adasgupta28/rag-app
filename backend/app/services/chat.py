"""Multi-turn RAG orchestration.

For each user message:
  1. Load recent history for the conversation.
  2. If there is history, have the LLM rewrite the message into a standalone query
     ("what about its limitations?" -> "What are the limitations of X?") so retrieval
     works on follow-ups.
  3. Retrieve the most relevant chunks for that query.
  4. Stream an answer grounded in those chunks, with numbered citations.
  5. Persist both messages, including the sources, so conversations can be reloaded.
"""

import json
import logging
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.context import AppContext
from app.db.models import Conversation, Message
from app.llm.client import ChatMessage
from app.llm.prompts import answer_messages, condense_messages
from app.retrieval.vector_store import RetrievedChunk

log = logging.getLogger(__name__)

_SNIPPET_CHARS = 500


def source_payload(chunks: list[RetrievedChunk]) -> list[dict]:
    return [
        {
            "n": i,
            "doc_id": c.doc_id,
            "filename": c.filename,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "score": c.score,
            "snippet": c.text[:_SNIPPET_CHARS],
        }
        for i, c in enumerate(chunks, 1)
    ]


def _title_from(question: str) -> str:
    title = " ".join(question.split())
    return title if len(title) <= 60 else title[:57].rstrip() + "..."


class ChatService:
    def __init__(self, ctx: AppContext):
        self._ctx = ctx

    def _history(self, session: Session, conversation_id: str) -> list[ChatMessage]:
        rows = session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(self._ctx.settings.history_messages)
        ).all()
        return [{"role": m.role, "content": m.content} for m in reversed(rows)]

    def standalone_query(self, history: list[ChatMessage], question: str) -> str:
        if not history:
            return question
        rewritten = self._ctx.llm.complete(condense_messages(history, question))
        return rewritten or question

    def stream_answer(self, question: str, conversation_id: str | None) -> Iterator[dict]:
        """Yields events: meta, sources, token (many), done, or error."""
        with Session(self._ctx.engine) as session:
            conversation = session.get(Conversation, conversation_id) if conversation_id else None
            if conversation is None:
                # Not persisted until the answer completes, so failed first turns leave no empty chats.
                conversation = Conversation(title=_title_from(question))

            try:
                history = self._history(session, conversation.id)
                query = self.standalone_query(history, question)
                chunks = self._ctx.retriever.retrieve(query)
            except Exception as exc:
                log.exception("Retrieval failed")
                yield {"event": "error", "data": {"message": f"Retrieval failed: {exc}"}}
                return

            sources = source_payload(chunks)
            yield {"event": "meta", "data": {"conversation_id": conversation.id, "query": query}}
            yield {"event": "sources", "data": sources}

            answer_parts: list[str] = []
            try:
                for token in self._ctx.llm.stream(answer_messages(history, question, chunks)):
                    answer_parts.append(token)
                    yield {"event": "token", "data": {"text": token}}
            except Exception as exc:
                log.exception("Generation failed")
                yield {"event": "error", "data": {"message": f"Generation failed: {exc}"}}
                return

            conversation.updated_at = datetime.now(timezone.utc)
            session.add(conversation)
            session.add(Message(conversation_id=conversation.id, role="user", content=question))
            assistant = Message(
                conversation_id=conversation.id,
                role="assistant",
                content="".join(answer_parts),
                sources_json=json.dumps(sources),
                rewritten_query=query if query != question else None,
            )
            session.add(assistant)
            session.commit()
            session.refresh(assistant)
            yield {"event": "done", "data": {"message_id": assistant.id}}
