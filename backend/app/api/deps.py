from collections.abc import Iterator

from fastapi import Request
from sqlmodel import Session

from app.context import AppContext


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def get_session(request: Request) -> Iterator[Session]:
    with Session(get_ctx(request).engine) as session:
        yield session
