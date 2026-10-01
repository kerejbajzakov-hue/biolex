"""Load data/seed.json into SQLite.

Usage:
    python -m app.seed            # add / update terms from seed.json
    python -m app.seed --reset    # wipe the database first
    python -m app.seed --file my_terms.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from . import db

SEED_FILE = db.BASE_DIR / "data" / "seed.json"


def _upsert_id(conn: sqlite3.Connection, table: str, slug: str, cols: dict) -> int:
    row = conn.execute(f"SELECT id FROM {table} WHERE slug = ?", (slug,)).fetchone()
    if row:
        if cols:
            sets = ", ".join(f"{k} = ?" for k in cols)
            conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*cols.values(), row["id"]))
        return row["id"]
    keys = ["slug", *cols.keys()]
    cur = conn.execute(
        f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
        (slug, *cols.values()),
    )
    return cur.lastrowid


def load(conn: sqlite3.Connection, data: dict) -> int:
    """Insert or update everything in `data`. Returns the number of terms loaded."""
    for lang in data.get("languages", []):
        conn.execute(
            "INSERT INTO languages(code, name) VALUES (?, ?) "
            "ON CONFLICT(code) DO UPDATE SET name = excluded.name",
            (lang["code"], lang["name"]),
        )

    theme_ids: dict[str, int] = {}
    for pos, th in enumerate(data.get("themes", [])):
        tid = _upsert_id(conn, "themes", th["slug"], {"icon": th["icon"], "position": pos})
        theme_ids[th["slug"]] = tid
        for lang, name in th["name"].items():
            conn.execute(
                "INSERT INTO theme_translations(theme_id, lang, name, description) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(theme_id, lang) DO UPDATE SET name = excluded.name, description = excluded.description",
                (tid, lang, name, th.get("description", {}).get(lang)),
            )

    for row in conn.execute("SELECT id, slug FROM themes"):
        theme_ids.setdefault(row["slug"], row["id"])

    term_ids: dict[str, int] = {}
    terms = data.get("terms", [])
    for t in terms:
        if t["theme"] not in theme_ids:
            raise ValueError(f"Term {t['slug']!r} uses unknown theme {t['theme']!r}")
        tid = _upsert_id(conn, "terms", t["slug"], {"theme_id": theme_ids[t["theme"]]})
        term_ids[t["slug"]] = tid
        for lang, name in t["name"].items():
            short = t["short"].get(lang) or t["short"]["en"]
            conn.execute(
                """INSERT INTO term_translations
                   (term_id, lang, name, name_norm, short_def, short_norm, definition, pronunciation, grammar, etymology)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(term_id, lang) DO UPDATE SET
                     name = excluded.name, name_norm = excluded.name_norm,
                     short_def = excluded.short_def, short_norm = excluded.short_norm,
                     definition = excluded.definition, pronunciation = excluded.pronunciation,
                     grammar = excluded.grammar, etymology = excluded.etymology""",
                (
                    tid, lang, name, db.normalize(name), short, db.normalize(short),
                    t.get("definition", {}).get(lang), t.get("pronunciation", {}).get(lang),
                    t.get("grammar", {}).get(lang), t.get("etymology", {}).get(lang),
                ),
            )
        conn.execute("DELETE FROM term_facts WHERE term_id = ?", (tid,))
        for lang, facts in t.get("facts", {}).items():
            for pos, text in enumerate(facts):
                conn.execute(
                    "INSERT INTO term_facts(term_id, lang, position, text) VALUES (?, ?, ?, ?)",
                    (tid, lang, pos, text),
                )

    for row in conn.execute("SELECT id, slug FROM terms"):
        term_ids.setdefault(row["slug"], row["id"])
    for t in terms:
        if "related" not in t:
            continue
        tid = term_ids[t["slug"]]
        conn.execute("DELETE FROM term_relations WHERE term_id = ?", (tid,))
        for pos, rel in enumerate(t["related"]):
            if rel in term_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO term_relations(term_id, related_id, position) VALUES (?, ?, ?)",
                    (tid, term_ids[rel], pos),
                )
    conn.commit()
    return len(terms)


def seed_if_empty(conn: sqlite3.Connection, path: Path = SEED_FILE) -> None:
    db.init_db(conn)
    if conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0] == 0:
        load(conn, json.loads(Path(path).read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Load BioLex terms into SQLite")
    parser.add_argument("--file", default=str(SEED_FILE))
    parser.add_argument("--db", default=None, help="database path (default: biolex.db)")
    parser.add_argument("--reset", action="store_true", help="delete existing data first")
    args = parser.parse_args()

    path = Path(args.db) if args.db else db.DEFAULT_DB_PATH
    if args.reset and path.exists():
        path.unlink()
    conn = db.connect(path)
    db.init_db(conn)
    n = load(conn, json.loads(Path(args.file).read_text(encoding="utf-8")))
    total = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
    print(f"Loaded {n} terms from {args.file}. Database now has {total} terms -> {path}")


if __name__ == "__main__":
    main()
