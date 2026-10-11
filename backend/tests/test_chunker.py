import pytest

from app.ingestion.chunker import chunk_pages, count_tokens
from app.ingestion.parser import Page


def _paragraph(word: str, n: int) -> str:
    return " ".join(f"{word}{i}." for i in range(n))


def test_small_document_is_single_chunk():
    chunks = chunk_pages([Page(1, ["Hello world.", "Second paragraph."])], chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world.\n\nSecond paragraph."
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 1)


def test_chunks_respect_size_and_track_pages():
    pages = [Page(n, [_paragraph(f"p{n}w", 30) for _ in range(3)]) for n in range(1, 5)]
    chunks = chunk_pages(pages, chunk_size=150, overlap=30)

    assert len(chunks) > 1
    assert all(c.token_count <= 160 for c in chunks)  # joins add a few separator tokens
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 4
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_consecutive_chunks_overlap():
    paragraphs = [f"Paragraph number {i} talks about topic {i}." for i in range(40)]
    chunks = chunk_pages([Page(1, paragraphs)], chunk_size=60, overlap=20)

    for prev, nxt in zip(chunks, chunks[1:]):
        last_paragraph_of_prev = prev.text.split("\n\n")[-1]
        assert last_paragraph_of_prev in nxt.text.split("\n\n")


def test_oversized_paragraph_is_split():
    huge = " ".join(["word"] * 1000)
    chunks = chunk_pages([Page(1, [huge])], chunk_size=100, overlap=0)
    assert len(chunks) >= 10
    assert all(count_tokens(c.text) <= 100 for c in chunks)


def test_empty_pages_produce_no_chunks():
    assert chunk_pages([Page(1, []), Page(2, [])]) == []


def test_overlap_must_be_smaller_than_chunk():
    with pytest.raises(ValueError):
        chunk_pages([Page(1, ["x"])], chunk_size=10, overlap=10)
