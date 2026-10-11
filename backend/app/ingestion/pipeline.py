import logging

from sqlmodel import Session

from app.context import AppContext
from app.db.models import Document, DocumentStatus
from app.ingestion.chunker import chunk_pages
from app.ingestion.parser import extract_pages

log = logging.getLogger(__name__)


class IngestionError(Exception):
    pass


def embedding_input(filename: str, text: str) -> str:
    # Prefixing the source name lets questions that mention a document by name match its chunks.
    return f"Document: {filename}\n\n{text}"


def ingest_document(ctx: AppContext, doc_id: str) -> None:
    """Parse, chunk, embed and index one document. Runs as a background task."""
    with Session(ctx.engine) as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            return
        try:
            pages = extract_pages(ctx.settings.docs_dir / doc.stored_name)
            chunks = chunk_pages(
                pages, ctx.settings.chunk_size_tokens, ctx.settings.chunk_overlap_tokens
            )
            if not chunks:
                raise IngestionError(
                    "No extractable text found. The PDF may be scanned images (OCR is not supported)."
                )
            embeddings = ctx.embedder.embed([embedding_input(doc.filename, c.text) for c in chunks])
            ctx.store.add(doc.id, doc.filename, chunks, embeddings)

            doc.page_count = len(pages)
            doc.chunk_count = len(chunks)
            doc.status = DocumentStatus.ready
            log.info("Ingested %s: %d pages, %d chunks", doc.filename, len(pages), len(chunks))
        except Exception as exc:
            log.exception("Ingestion failed for %s", doc.filename)
            ctx.store.delete_document(doc.id)  # remove any partially written vectors
            doc.status = DocumentStatus.failed
            doc.error = str(exc) or exc.__class__.__name__
        session.add(doc)
        session.commit()
