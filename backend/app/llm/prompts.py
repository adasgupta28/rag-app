from app.llm.client import ChatMessage
from app.retrieval.vector_store import RetrievedChunk

CONDENSE_SYSTEM = """You rewrite follow-up questions for a document search engine.
Given a conversation and the user's latest message, rewrite the latest message as a single
standalone question that can be understood without the conversation. Resolve pronouns and
references ("it", "that section", "the second one") using the conversation.
If the latest message is already standalone, return it unchanged.
Return only the rewritten question, with no preamble."""

ANSWER_SYSTEM = """You are PaperTrail, an assistant that answers questions using excerpts from the user's documents.

Rules:
- Base every factual statement on the numbered excerpts provided in the latest user message.
- Cite sources inline with their bracketed number, e.g. "Revenue grew 12% [2]." Cite each claim; combine like [1][3] when several excerpts support it.
- If the excerpts do not contain the answer, say you could not find it in the uploaded documents. Do not use outside knowledge to fill gaps.
- Use the earlier conversation only to understand what the user is asking about.
- Be concise. Use short paragraphs or bullet lists where helpful."""

NO_CONTEXT_NOTE = "(No relevant excerpts were found in the uploaded documents.)"


def _page_label(chunk: RetrievedChunk) -> str:
    if chunk.page_start == chunk.page_end:
        return f"p. {chunk.page_start}"
    return f"pp. {chunk.page_start}-{chunk.page_end}"


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return NO_CONTEXT_NOTE
    return "\n\n".join(
        f"[{i}] {chunk.filename}, {_page_label(chunk)}\n{chunk.text}" for i, chunk in enumerate(chunks, 1)
    )


def condense_messages(history: list[ChatMessage], question: str) -> list[ChatMessage]:
    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    return [
        {"role": "system", "content": CONDENSE_SYSTEM},
        {"role": "user", "content": f"Conversation:\n{transcript}\n\nLatest message: {question}"},
    ]


def answer_messages(history: list[ChatMessage], question: str, chunks: list[RetrievedChunk]) -> list[ChatMessage]:
    return [
        {"role": "system", "content": ANSWER_SYSTEM},
        *history,
        {
            "role": "user",
            "content": f"Excerpts:\n\n{format_context(chunks)}\n\n---\nQuestion: {question}",
        },
    ]
