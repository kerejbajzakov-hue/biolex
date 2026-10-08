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
from .schemas import Language, Stats, TermDetail, TermIn, TermList, TermSource, TermSummary, Theme
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
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"])

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

    # ---------- user terms ----------

    def _payload(body: TermIn) -> dict:
        return {
            "theme": body.theme,
            "translations": {lang: tr.model_dump() for lang, tr in body.translations.items()},
            "related": body.related,
        }

    @app.post("/api/terms", response_model=TermDetail, status_code=201, tags=["my terms"])
    def create_term(body: TermIn, lang: Lang = "en", conn=Depends(get_conn)):
        """Add your own term (in one, two or all three languages)."""
        try:
            slug = repo.create_term(conn, _payload(body))
        except ValueError as e:
            raise HTTPException(422, str(e))
        return repo.get_term(conn, slug, lang)

    @app.get("/api/terms/{slug}/source", response_model=TermSource, tags=["my terms"])
    def term_source(slug: str, conn=Depends(get_conn)):
        """All languages of a term as entered — used by the edit form."""
        found = repo.get_term_source(conn, slug)
        if not found:
            raise HTTPException(404, "Term not found")
        return found

    @app.put("/api/terms/{slug}", response_model=TermDetail, tags=["my terms"])
    def update_term(slug: str, body: TermIn, lang: Lang = "en", conn=Depends(get_conn)):
        try:
            if not repo.update_term(conn, slug, _payload(body)):
                raise HTTPException(404, "Term not found")
        except repo.NotEditable:
            raise HTTPException(403, "Built-in dictionary terms can't be changed")
        except ValueError as e:
            raise HTTPException(422, str(e))
        return repo.get_term(conn, slug, lang)

    @app.delete("/api/terms/{slug}", status_code=204, tags=["my terms"])
    def delete_term(slug: str, conn=Depends(get_conn)):
        try:
            if not repo.delete_term(conn, slug):
                raise HTTPException(404, "Term not found")
        except repo.NotEditable:
            raise HTTPException(403, "Built-in dictionary terms can't be deleted")

    @app.get("/api/my-terms", response_model=list[TermSummary], tags=["my terms"])
    def my_terms(lang: Lang = "en", conn=Depends(get_conn)):
        slugs = [r["slug"] for r in conn.execute("SELECT slug FROM terms WHERE is_custom = 1 ORDER BY id DESC")]
        return repo.terms_by_slugs(conn, lang, slugs)

    # The web app (index.html + assets) is served from /
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="web")
    return app


app = create_app()
