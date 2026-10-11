import hashlib
import math
import re
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

_DIM = 256


class FakeEmbedder:
    """Hashed bag-of-words vectors: texts sharing words get similar vectors, so retrieval is testable offline."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * _DIM
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % _DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class FakeLLM:
    def __init__(self):
        self.complete_calls: list[list[dict]] = []
        self.stream_calls: list[list[dict]] = []
        self.rewrite_to: str | None = None

    def complete(self, messages):
        self.complete_calls.append(messages)
        return self.rewrite_to or "standalone question"

    def stream(self, messages):
        self.stream_calls.append(messages)
        yield from ["The answer ", "is here ", "[1]."]


def make_pdf(path: Path, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=11)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test",
        docs_dir=tmp_path / "docs",
        data_dir=tmp_path / "data",
        chunk_size_tokens=120,
        chunk_overlap_tokens=20,
        min_relevance=0.0,
    )


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(settings: Settings, fake_llm: FakeLLM) -> TestClient:
    app = create_app(settings, embedder=FakeEmbedder(), llm=fake_llm)
    return TestClient(app)
