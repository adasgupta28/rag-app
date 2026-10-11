from app.retrieval.embedder import Embedder
from app.retrieval.vector_store import RetrievedChunk, VectorStore


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStore, top_k: int, min_relevance: float):
        self._embedder = embedder
        self._store = store
        self._top_k = top_k
        self._min_relevance = min_relevance

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        [embedding] = self._embedder.embed([query])
        hits = self._store.query(embedding, self._top_k)
        return [h for h in hits if h.score >= self._min_relevance]
