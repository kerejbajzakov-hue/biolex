"""BioLex — FastAPI backend.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterator, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import db, repository as repo
from .schemas import Language, Stats, TermDetail, TermList, TermSummary, Theme
from .seed import seed_if_empty

Lang = Literal["en", "kk", "ru"]
STATIC_DIR = db.BASE_DIR / "static"


def create_app(db_path: str | Path | None = None) -> FastAPI:
    path = Path(db_path) if db_path else db.DEFAULT_DB_PATH

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        conn = db.connect(path)
        seed_if_empty(conn)
        conn.close()
        yield

    app = FastAPI(
        title="BioLex API",
        version="1.0.0",
        description="Trilingual (English / Қазақша / Русский) biology dictionary.",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = db.connect(path)
        try:
            yield conn
        finally:
            conn.close()

    @app.get("/api/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    @app.get("/api/languages", response_model=list[Language], tags=["meta"])
    def languages(conn=Depends(get_conn)):
        return [dict(r) for r in conn.execute("SELECT code, name FROM languages ORDER BY rowid")]

    @app.get("/api/stats", response_model=Stats, tags=["meta"])
    def stats(lang: Lang = "en", conn=Depends(get_conn)):
        """How many terms the dictionary has — total, per theme and per language."""
        return repo.stats(conn, lang)

    @app.get("/api/themes", response_model=list[Theme], tags=["themes"])
    def themes(lang: Lang = "en", conn=Depends(get_conn)):
        return repo.list_themes(conn, lang)

    @app.get("/api/themes/{slug}", response_model=Theme, tags=["themes"])
    def theme(slug: str, lang: Lang = "en", conn=Depends(get_conn)):
        found = repo.get_theme(conn, slug, lang)
        if not found:
            raise HTTPException(404, "Theme not found")
        return found

    @app.get("/api/terms", response_model=TermList, tags=["terms"])
    def terms(
        lang: Lang = "en",
        q: str = Query("", max_length=80, description="Search text (name or definition)"),
        theme: str | None = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        conn=Depends(get_conn),
    ):
        return repo.search_terms(conn, lang, q, theme, limit, offset)

    @app.get("/api/terms/batch", response_model=list[TermSummary], tags=["terms"])
    def terms_batch(slugs: str = Query("", description="Comma-separated slugs"), lang: Lang = "en", conn=Depends(get_conn)):
        """Used by the Saved screen."""
        wanted = [s for s in slugs.split(",") if s][:200]
        return repo.terms_by_slugs(conn, lang, wanted)

    @app.get("/api/terms/today", response_model=TermDetail, tags=["terms"])
    def today(lang: Lang = "en", conn=Depends(get_conn)):
        found = repo.term_of_the_day(conn, lang)
        if not found:
            raise HTTPException(404, "Dictionary is empty")
        return found

    @app.get("/api/terms/{slug}", response_model=TermDetail, tags=["terms"])
    def term(slug: str, lang: Lang = "en", conn=Depends(get_conn)):
        found = repo.get_term(conn, slug, lang)
        if not found:
            raise HTTPException(404, "Term not found")
        return found

    # The web app (index.html + assets) is served from /
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
    return app


app = create_app()
