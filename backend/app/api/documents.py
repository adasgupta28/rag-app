import hashlib
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import get_ctx, get_session
from app.context import AppContext
from app.db.models import Document, DocumentStatus
from app.ingestion.pipeline import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])

_READ_BLOCK = 1024 * 1024
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class DocumentOut(BaseModel):
    id: str
    filename: str
    size_bytes: int
    page_count: int | None
    chunk_count: int | None
    status: DocumentStatus
    error: str | None
    created_at: datetime


def _safe_name(filename: str) -> str:
    stem = _UNSAFE_CHARS.sub("_", Path(filename).stem).strip("._") or "document"
    return f"{stem[:80]}.pdf"


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentOut)
async def upload_document(
    file: UploadFile,
    background: BackgroundTasks,
    ctx: AppContext = Depends(get_ctx),
    session: Session = Depends(get_session),
) -> Document:
    filename = Path(file.filename or "document.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF files are supported.")

    # Read in blocks so we can enforce the size limit and hash without trusting headers.
    max_bytes = ctx.settings.max_upload_mb * 1024 * 1024
    digest = hashlib.sha256()
    content = bytearray()
    while block := await file.read(_READ_BLOCK):
        content.extend(block)
        if len(content) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"File exceeds the {ctx.settings.max_upload_mb} MB limit.",
            )
        digest.update(block)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File is not a valid PDF.")

    sha256 = digest.hexdigest()
    existing = session.exec(select(Document).where(Document.sha256 == sha256)).first()
    if existing is not None:
        if existing.status != DocumentStatus.failed:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"This file was already uploaded as '{existing.filename}'."
            )
        _remove_document(ctx, session, existing)  # allow retrying a failed upload

    doc = Document(filename=filename, stored_name="", sha256=sha256, size_bytes=len(content))
    doc.stored_name = f"{doc.id[:8]}_{_safe_name(filename)}"
    ctx.settings.docs_dir.mkdir(parents=True, exist_ok=True)
    (ctx.settings.docs_dir / doc.stored_name).write_bytes(content)

    session.add(doc)
    session.commit()
    session.refresh(doc)
    background.add_task(ingest_document, ctx, doc.id)
    return doc


@router.get("", response_model=list[DocumentOut])
def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    return list(session.exec(select(Document).order_by(Document.created_at.desc())).all())


def _get_or_404(session: Session, doc_id: str) -> Document:
    doc = session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    return doc


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, session: Session = Depends(get_session)) -> Document:
    return _get_or_404(session, doc_id)


@router.get("/{doc_id}/file")
def get_document_file(
    doc_id: str, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)
) -> FileResponse:
    doc = _get_or_404(session, doc_id)
    path = ctx.settings.docs_dir / doc.stored_name
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File is missing from the docs folder.")
    # inline so the browser's PDF viewer opens it (and honours #page=N for citations)
    return FileResponse(
        path, media_type="application/pdf", filename=doc.filename, content_disposition_type="inline"
    )


def _remove_document(ctx: AppContext, session: Session, doc: Document) -> None:
    ctx.store.delete_document(doc.id)
    (ctx.settings.docs_dir / doc.stored_name).unlink(missing_ok=True)
    session.delete(doc)
    session.commit()


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: str, ctx: AppContext = Depends(get_ctx), session: Session = Depends(get_session)
) -> None:
    doc = _get_or_404(session, doc_id)
    if doc.status == DocumentStatus.processing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Wait for processing to finish before deleting.")
    _remove_document(ctx, session, doc)
