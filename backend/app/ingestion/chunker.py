"""Token-aware chunking that respects paragraph and sentence boundaries.

Strategy:
  1. Break each page into paragraphs (from the PDF layout).
  2. Paragraphs that are too large get split into sentences, and sentences that are
     still too large get split on raw token boundaries as a last resort.
  3. Greedily pack these segments into chunks of up to `chunk_size` tokens, carrying
     the trailing `overlap` tokens' worth of segments into the next chunk so that facts
     straddling a boundary are retrievable from either side.
Each chunk records the page range it came from, which is what powers citations.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from app.ingestion.parser import Page

# text-embedding-3-* models use the cl100k_base tokenizer.
_ENCODING_NAME = "cl100k_base"
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


@lru_cache
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING_NAME)


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text))


@dataclass
class Chunk:
    index: int
    text: str
    page_start: int
    page_end: int
    token_count: int


@dataclass
class _Segment:
    text: str
    page: int
    tokens: int


def _split_oversized(text: str, page: int, max_tokens: int) -> list[_Segment]:
    segments: list[_Segment] = []
    for sentence in _SENTENCE_END.split(text):
        tokens = count_tokens(sentence)
        if tokens <= max_tokens:
            segments.append(_Segment(sentence, page, tokens))
            continue
        ids = _encoding().encode(sentence)
        for start in range(0, len(ids), max_tokens):
            piece = _encoding().decode(ids[start : start + max_tokens])
            segments.append(_Segment(piece, page, count_tokens(piece)))
    return segments


def _segments(pages: list[Page], max_tokens: int) -> list[_Segment]:
    segments: list[_Segment] = []
    for page in pages:
        for paragraph in page.paragraphs:
            tokens = count_tokens(paragraph)
            if tokens <= max_tokens:
                segments.append(_Segment(paragraph, page.number, tokens))
            else:
                segments.extend(_split_oversized(paragraph, page.number, max_tokens))
    return segments


def chunk_pages(pages: list[Page], chunk_size: int = 600, overlap: int = 100) -> list[Chunk]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    window: list[_Segment] = []
    window_tokens = 0
    has_new_content = False  # avoid emitting a final chunk made only of overlap

    def emit() -> None:
        text = "\n\n".join(s.text for s in window)
        chunks.append(
            Chunk(
                index=len(chunks),
                text=text,
                page_start=window[0].page,
                page_end=window[-1].page,
                token_count=count_tokens(text),
            )
        )

    for segment in _segments(pages, chunk_size):
        if window and window_tokens + segment.tokens > chunk_size:
            emit()
            # Keep trailing segments that fit within the overlap budget.
            carried: list[_Segment] = []
            carried_tokens = 0
            for prev in reversed(window):
                if carried_tokens + prev.tokens > overlap:
                    break
                carried.insert(0, prev)
                carried_tokens += prev.tokens
            window, window_tokens = carried, carried_tokens
            # Drop overlap if it would push the next segment past the limit.
            while window and window_tokens + segment.tokens > chunk_size:
                window_tokens -= window.pop(0).tokens
            has_new_content = False

        window.append(segment)
        window_tokens += segment.tokens
        has_new_content = True

    if window and has_new_content:
        emit()
    return chunks
