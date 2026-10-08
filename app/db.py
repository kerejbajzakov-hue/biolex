"""SQLite connection helpers and schema for BioLex."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(os.environ.get("BIOLEX_DB", BASE_DIR / "biolex.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS languages (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS themes (
    id       INTEGER PRIMARY KEY,
    slug     TEXT NOT NULL UNIQUE,
    icon     TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS theme_translations (
    theme_id    INTEGER NOT NULL REFERENCES themes(id) ON DELETE CASCADE,
    lang        TEXT NOT NULL REFERENCES languages(code),
    name        TEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (theme_id, lang)
);

CREATE TABLE IF NOT EXISTS terms (
    id         INTEGER PRIMARY KEY,
    slug       TEXT NOT NULL UNIQUE,
    theme_id   INTEGER NOT NULL REFERENCES themes(id),
    is_custom  INTEGER NOT NULL DEFAULT 0,   -- 1 = added by a user in the app
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_terms_theme ON terms(theme_id);

-- One row per term per language. *_norm columns hold casefolded text so
-- search works for Cyrillic too (SQLite's LIKE only folds ASCII).
CREATE TABLE IF NOT EXISTS term_translations (
    term_id       INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    lang          TEXT NOT NULL REFERENCES languages(code),
    name          TEXT NOT NULL,
    name_norm     TEXT NOT NULL,
    short_def     TEXT NOT NULL,
    short_norm    TEXT NOT NULL,
    definition    TEXT,
    pronunciation TEXT,
    grammar       TEXT,
    etymology     TEXT,
    PRIMARY KEY (term_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_tt_lang_name ON term_translations(lang, name_norm);

CREATE TABLE IF NOT EXISTS term_facts (
    id       INTEGER PRIMARY KEY,
    term_id  INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    lang     TEXT NOT NULL REFERENCES languages(code),
    position INTEGER NOT NULL,
    text     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_term ON term_facts(term_id, lang);

CREATE TABLE IF NOT EXISTS term_relations (
    term_id    INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    related_id INTEGER NOT NULL REFERENCES terms(id) ON DELETE CASCADE,
    position   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (term_id, related_id)
);
"""


def normalize(text: str | None) -> str:
    """Casefold for search; treat ё as е so Russian search is forgiving."""
    return (text or "").casefold().replace("ё", "е").strip()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or DEFAULT_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # databases created before user terms existed get the new column
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(terms)")}
    if "is_custom" not in cols:
        conn.execute("ALTER TABLE terms ADD COLUMN is_custom INTEGER NOT NULL DEFAULT 0")
    conn.commit()
