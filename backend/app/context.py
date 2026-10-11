from dataclasses import dataclass

from sqlalchemy import Engine

from app.config import Settings
from app.llm.client import LLM
from app.retrieval.embedder import Embedder
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import VectorStore


@dataclass
class AppContext:
    """Long-lived services shared by request handlers and background jobs."""

    settings: Settings
    engine: Engine
    store: VectorStore
    embedder: Embedder
    llm: LLM

    @property
    def retriever(self) -> Retriever:
        return Retriever(self.embedder, self.store, self.settings.top_k, self.settings.min_relevance)
