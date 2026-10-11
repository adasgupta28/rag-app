from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a .env file at the repo root."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    openai_api_key: str = ""
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"

    docs_dir: Path = REPO_ROOT / "docs"
    data_dir: Path = REPO_ROOT / "data"

    # Chunking: sized in tokens so chunks map predictably onto model context limits.
    chunk_size_tokens: int = 600
    chunk_overlap_tokens: int = 100

    # Retrieval
    top_k: int = 6
    min_relevance: float = 0.2  # cosine similarity floor; weaker matches are dropped

    # Chat: how many previous messages are sent to the LLM (user + assistant each count as one).
    history_messages: int = 8

    max_upload_mb: int = 50
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'papertrail.db').as_posix()}"

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"


@lru_cache
def get_settings() -> Settings:
    return Settings()
