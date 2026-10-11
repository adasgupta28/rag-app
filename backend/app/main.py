import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from app.api import chat, conversations, documents
from app.api.deps import get_ctx
from app.config import Settings, get_settings
from app.context import AppContext
from app.db.session import create_db_engine, fail_interrupted_ingestions
from app.llm.client import LLM, OpenAIChat
from app.retrieval.embedder import Embedder, OpenAIEmbedder
from app.retrieval.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(
    settings: Settings | None = None,
    *,
    embedder: Embedder | None = None,
    llm: LLM | None = None,
) -> FastAPI:
    """App factory. Tests inject fake embedder/LLM implementations; production uses OpenAI."""
    settings = settings or get_settings()
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    if embedder is None or llm is None:
        # api_key placeholder lets the server start (and serve /health) before a key is configured.
        client = OpenAI(api_key=settings.openai_api_key or "missing-key")
        embedder = embedder or OpenAIEmbedder(client, settings.embedding_model)
        llm = llm or OpenAIChat(client, settings.chat_model)

    engine = create_db_engine(settings.sqlite_url)
    fail_interrupted_ingestions(engine)

    app = FastAPI(title="PaperTrail API", version="0.1.0")
    app.state.ctx = AppContext(
        settings=settings,
        engine=engine,
        store=VectorStore(settings.chroma_dir),
        embedder=embedder,
        llm=llm,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")
    api.include_router(documents.router)
    api.include_router(conversations.router)
    api.include_router(chat.router)

    @api.get("/health", tags=["meta"])
    def health(ctx: AppContext = Depends(get_ctx)) -> dict:
        return {
            "status": "ok",
            "openai_configured": bool(ctx.settings.openai_api_key),
            "chat_model": ctx.settings.chat_model,
            "embedding_model": ctx.settings.embedding_model,
            "indexed_chunks": ctx.store.count(),
        }

    app.include_router(api)
    return app

