from dataclasses import asdict, dataclass
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.ingestion.chunker import Chunk

_MAX_BATCH = 1000


@dataclass
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    filename: str
    page_start: int
    page_end: int
    text: str
    score: float  # cosine similarity, 1.0 = identical direction

    def to_dict(self) -> dict:
        return asdict(self)


class VectorStore:
    """Thin wrapper over a ChromaDB collection. Embeddings are computed by us, not by Chroma,
    so the embedding model is explicit and swappable."""

    def __init__(self, persist_dir: Path, collection: str = "papertrail_chunks"):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(persist_dir), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._client.get_or_create_collection(
            collection,
            configuration={"hnsw": {"space": "cosine"}},
            embedding_function=None,
        )

    def add(self, doc_id: str, filename: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        for start in range(0, len(chunks), _MAX_BATCH):
            batch = chunks[start : start + _MAX_BATCH]
            self._collection.add(
                ids=[f"{doc_id}:{c.index}" for c in batch],
                embeddings=embeddings[start : start + _MAX_BATCH],
                documents=[c.text for c in batch],
                metadatas=[
                    {
                        "doc_id": doc_id,
                        "filename": filename,
                        "page_start": c.page_start,
                        "page_end": c.page_end,
                        "chunk_index": c.index,
                    }
                    for c in batch
                ],
            )

    def query(self, embedding: list[float], k: int) -> list[RetrievedChunk]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=meta["doc_id"],
                filename=meta["filename"],
                page_start=meta["page_start"],
                page_end=meta["page_end"],
                text=text,
                score=round(1.0 - distance, 4),
            )
            for chunk_id, text, meta, distance in zip(
                result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
        ]

    def delete_document(self, doc_id: str) -> None:
        self._collection.delete(where={"doc_id": doc_id})

    def count(self) -> int:
        return self._collection.count()
