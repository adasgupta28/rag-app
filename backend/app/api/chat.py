import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_ctx
from app.context import AppContext
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


def _sse(events: Iterator[dict]) -> Iterator[str]:
    for event in events:
        yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"


@router.post("/chat")
def chat(request: ChatRequest, ctx: AppContext = Depends(get_ctx)) -> StreamingResponse:
    """Answer a question as a Server-Sent Events stream.

    Events: `meta` (conversation id, rewritten query), `sources` (retrieved excerpts),
    `token` (answer text deltas), then `done` or `error`.
    """
    events = ChatService(ctx).stream_answer(request.question.strip(), request.conversation_id)
    return StreamingResponse(
        _sse(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
