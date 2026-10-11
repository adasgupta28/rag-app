from sqlalchemy import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.models import Document, DocumentStatus


def create_db_engine(url: str) -> Engine:
    # check_same_thread=False: ingestion runs in background threads.
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def fail_interrupted_ingestions(engine: Engine) -> None:
    """Documents left in 'processing' when the server stopped will never finish; mark them failed."""
    with Session(engine) as session:
        stuck = session.exec(
            select(Document).where(Document.status == DocumentStatus.processing)
        ).all()
        for doc in stuck:
            doc.status = DocumentStatus.failed
            doc.error = "Ingestion was interrupted by a server restart. Delete and re-upload."
            session.add(doc)
        session.commit()
