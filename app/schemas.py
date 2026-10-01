"""Response models (shown in the auto-generated /docs)."""
from __future__ import annotations

from pydantic import BaseModel


class Language(BaseModel):
    code: str
    name: str


class ThemeRef(BaseModel):
    slug: str
    name: str
    icon: str


class Theme(BaseModel):
    slug: str
    icon: str
    name: str
    description: str | None = None
    term_count: int


class TermSummary(BaseModel):
    slug: str
    name: str
    short_def: str
    theme: ThemeRef


class TermList(BaseModel):
    query: str
    theme: str | None
    total: int
    items: list[TermSummary]


class TermDetail(TermSummary):
    definition: str | None = None
    pronunciation: str | None = None
    grammar: str | None = None
    etymology: str | None = None
    facts: list[str] = []
    related: list[TermSummary] = []
    languages: list[str] = []
    translated: bool = True


class ThemeCount(BaseModel):
    slug: str
    name: str
    term_count: int


class LanguageCount(BaseModel):
    name: str
    translated: int


class Stats(BaseModel):
    total_terms: int
    total_themes: int
    by_theme: list[ThemeCount]
    by_language: dict[str, LanguageCount]
    terms_with_full_article: int
