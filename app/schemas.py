"""Response models (shown in the auto-generated /docs)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    custom: bool = False


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
    custom_terms: int = 0


# ---------- user terms ----------

class TranslationIn(BaseModel):
    name: str = Field("", max_length=120)
    short_def: str = Field("", max_length=400)
    definition: str | None = Field(None, max_length=4000)
    pronunciation: str | None = Field(None, max_length=120)
    etymology: str | None = Field(None, max_length=600)
    facts: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("facts")
    @classmethod
    def _facts(cls, v: list[str]) -> list[str]:
        return [f.strip()[:400] for f in v if f and f.strip()]

    def is_filled(self) -> bool:
        return bool(self.name.strip() and self.short_def.strip())

    def is_empty(self) -> bool:
        return not any([self.name.strip(), self.short_def.strip(), (self.definition or "").strip(),
                        (self.pronunciation or "").strip(), (self.etymology or "").strip(), self.facts])


class TermIn(BaseModel):
    """A term written by a user. Fill at least one language; empty languages are dropped."""
    theme: str
    translations: dict[Literal["en", "kk", "ru"], TranslationIn]
    related: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _check(self):
        kept = {}
        for lang, tr in self.translations.items():
            if tr.is_empty():
                continue
            if not tr.is_filled():
                raise ValueError(f"{lang}: both the term and its short definition are needed")
            kept[lang] = tr
        if not kept:
            raise ValueError("Fill in the term and a short definition in at least one language")
        self.translations = kept
        return self


class TranslationSource(BaseModel):
    name: str
    short_def: str
    definition: str | None = None
    pronunciation: str | None = None
    etymology: str | None = None
    facts: list[str] = []


class TermSource(BaseModel):
    slug: str
    theme: str
    custom: bool
    translations: dict[str, TranslationSource]
    related: list[str] = []
