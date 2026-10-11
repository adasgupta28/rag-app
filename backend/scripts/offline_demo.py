"""Run the API with fake (offline) embeddings and LLM, for UI work without an OpenAI key.

Retrieval uses hashed bag-of-words vectors, and the "LLM" returns a canned answer citing [1].
Data goes to ./offline_demo_data (gitignored), separate from the real docs/ and data/ folders.

    cd backend
    uv run python scripts/offline_demo.py
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import uvicorn  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.conftest import FakeEmbedder, FakeLLM  # noqa: E402

if __name__ == "__main__":
    root = BACKEND / "offline_demo_data"
    settings = Settings(
        _env_file=None,
        openai_api_key="offline",
        docs_dir=root / "docs",
        data_dir=root / "data",
        min_relevance=0.0,
    )
    uvicorn.run(create_app(settings, embedder=FakeEmbedder(), llm=FakeLLM()), port=8000)
