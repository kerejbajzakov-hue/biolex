"""All SQL lives here. Every query falls back to English if a translation is missing."""
from __future__ import annotations

import datetime as dt
import sqlite3

from .db import normalize

ALPHABETS = {
    "en": "abcdefghijklmnopqrstuvwxyz",
    "kk": "аәбвгғдеёжзийкқлмнңоөпрстуұүфхһцчшщъыіьэюя",
    "ru": "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
}


def sort_key(lang: str, text: str) -> tuple:
    """Order words by the language's own alphabet (Kazakh letters like Ә, Қ sit in their real place)."""
    alpha = ALPHABETS.get(lang, ALPHABETS["en"])
    return tuple(alpha.index(c) if c in alpha else 1000 + ord(c) for c in text.casefold())


def _like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------- themes & counts ----------

def list_themes(conn: sqlite3.Connection, lang: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT th.slug, th.icon,
               COALESCE(tl.name, te.name) AS name,
               COALESCE(tl.description, te.description) AS description,
               (SELECT COUNT(*) FROM terms t WHERE t.theme_id = th.id) AS term_count
        FROM themes th
        LEFT JOIN theme_translations tl ON tl.theme_id = th.id AND tl.lang = ?
        LEFT JOIN theme_translations te ON te.theme_id = th.id AND te.lang = 'en'
        ORDER BY th.position, th.slug
        """,
        (lang,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_theme(conn: sqlite3.Connection, slug: str, lang: str) -> dict | None:
    return next((t for t in list_themes(conn, lang) if t["slug"] == slug), None)


def stats(conn: sqlite3.Connection, lang: str) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
    per_lang = {
        r["code"]: {"name": r["name"], "translated": r["n"]}
        for r in conn.execute(
            """SELECT l.code, l.name, COUNT(tt.term_id) AS n
               FROM languages l LEFT JOIN term_translations tt ON tt.lang = l.code
               GROUP BY l.code ORDER BY l.rowid"""
        )
    }
    themes = list_themes(conn, lang)
    with_details = conn.execute(
        "SELECT COUNT(DISTINCT term_id) FROM term_translations WHERE definition IS NOT NULL AND lang = ?",
        (lang,),
    ).fetchone()[0]
    return {
        "total_terms": total,
        "total_themes": len(themes),
        "by_theme": [{"slug": t["slug"], "name": t["name"], "term_count": t["term_count"]} for t in themes],
        "by_language": per_lang,
        "terms_with_full_article": with_details,
    }


# ---------- terms ----------

_TERM_SELECT = """
SELECT t.id, t.slug, th.slug AS theme_slug, th.icon AS theme_icon,
       COALESCE(tl.name, te.name)            AS name,
       COALESCE(tl.name_norm, te.name_norm)  AS name_norm,
       COALESCE(tl.short_def, te.short_def)  AS short_def,
       COALESCE(tl.short_norm, te.short_norm) AS short_norm,
       COALESCE(hl.name, he.name)            AS theme_name
FROM terms t
JOIN themes th ON th.id = t.theme_id
LEFT JOIN term_translations tl ON tl.term_id = t.id AND tl.lang = :lang
LEFT JOIN term_translations te ON te.term_id = t.id AND te.lang = 'en'
LEFT JOIN theme_translations hl ON hl.theme_id = th.id AND hl.lang = :lang
LEFT JOIN theme_translations he ON he.theme_id = th.id AND he.lang = 'en'
"""


def _summary(row: sqlite3.Row) -> dict:
    return {
        "slug": row["slug"],
        "name": row["name"],
        "short_def": row["short_def"],
        "theme": {"slug": row["theme_slug"], "name": row["theme_name"], "icon": row["theme_icon"]},
    }


def search_terms(
    conn: sqlite3.Connection,
    lang: str,
    q: str = "",
    theme: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    qn = normalize(q)
    where, params = [], {"lang": lang}
    if theme:
        where.append("th.slug = :theme")
        params["theme"] = theme
    if qn:
        params["contains"] = f"%{_like(qn)}%"
        where.append(
            "(COALESCE(tl.name_norm, te.name_norm) LIKE :contains ESCAPE '\\' "
            "OR COALESCE(tl.short_norm, te.short_norm) LIKE :contains ESCAPE '\\')"
        )
    sql = _TERM_SELECT + (" WHERE " + " AND ".join(where) if where else "")
    rows = conn.execute(sql, params).fetchall()

    def rank(r: sqlite3.Row) -> tuple:
        name = r["name_norm"]
        if not qn:
            level = 0
        elif name.startswith(qn):
            level = 0
        elif any(w.startswith(qn) for w in name.split()):
            level = 1
        elif qn in name:
            level = 2
        else:
            level = 3  # matched in the definition only
        return (level, sort_key(lang, r["name"]))

    rows.sort(key=rank)
    return {
        "query": q,
        "theme": theme,
        "total": len(rows),
        "items": [_summary(r) for r in rows[offset: offset + limit]],
    }


def terms_by_slugs(conn: sqlite3.Connection, lang: str, slugs: list[str]) -> list[dict]:
    if not slugs:
        return []
    marks = ",".join(f":s{i}" for i in range(len(slugs)))
    params = {"lang": lang, **{f"s{i}": s for i, s in enumerate(slugs)}}
    rows = {r["slug"]: r for r in conn.execute(_TERM_SELECT + f" WHERE t.slug IN ({marks})", params)}
    return [_summary(rows[s]) for s in slugs if s in rows]


def get_term(conn: sqlite3.Connection, slug: str, lang: str) -> dict | None:
    row = conn.execute(
        """
        SELECT t.id, t.slug, th.slug AS theme_slug, th.icon AS theme_icon,
               COALESCE(hl.name, he.name) AS theme_name,
               COALESCE(tl.name, te.name) AS name,
               COALESCE(tl.short_def, te.short_def) AS short_def,
               COALESCE(tl.definition, tl.short_def, te.definition, te.short_def) AS definition,
               COALESCE(tl.pronunciation, te.pronunciation) AS pronunciation,
               tl.grammar AS grammar,
               COALESCE(tl.etymology, te.etymology) AS etymology,
               (tl.term_id IS NOT NULL) AS translated
        FROM terms t
        JOIN themes th ON th.id = t.theme_id
        LEFT JOIN term_translations tl ON tl.term_id = t.id AND tl.lang = :lang
        LEFT JOIN term_translations te ON te.term_id = t.id AND te.lang = 'en'
        LEFT JOIN theme_translations hl ON hl.theme_id = th.id AND hl.lang = :lang
        LEFT JOIN theme_translations he ON he.theme_id = th.id AND he.lang = 'en'
        WHERE t.slug = :slug
        """,
        {"lang": lang, "slug": slug},
    ).fetchone()
    if not row:
        return None

    facts = [r["text"] for r in conn.execute(
        "SELECT text FROM term_facts WHERE term_id = ? AND lang = ? ORDER BY position", (row["id"], lang))]
    if not facts:
        facts = [r["text"] for r in conn.execute(
            "SELECT text FROM term_facts WHERE term_id = ? AND lang = 'en' ORDER BY position", (row["id"],))]
    related_slugs = [r["slug"] for r in conn.execute(
        """SELECT t.slug FROM term_relations r JOIN terms t ON t.id = r.related_id
           WHERE r.term_id = ? ORDER BY r.position""", (row["id"],))]
    available = [r["lang"] for r in conn.execute(
        "SELECT lang FROM term_translations WHERE term_id = ? ORDER BY lang", (row["id"],))]

    return {
        "slug": row["slug"],
        "name": row["name"],
        "short_def": row["short_def"],
        "definition": row["definition"],
        "pronunciation": row["pronunciation"],
        "grammar": row["grammar"],
        "etymology": row["etymology"],
        "facts": facts,
        "theme": {"slug": row["theme_slug"], "name": row["theme_name"], "icon": row["theme_icon"]},
        "related": terms_by_slugs(conn, lang, related_slugs),
        "languages": available,
        "translated": bool(row["translated"]),
    }


def term_of_the_day(conn: sqlite3.Connection, lang: str, day: dt.date | None = None) -> dict | None:
    """Same term for everyone on a given day, rotating through the whole dictionary."""
    day = day or dt.date.today()
    slugs = [r["slug"] for r in conn.execute("SELECT slug FROM terms ORDER BY id")]
    if not slugs:
        return None
    return get_term(conn, slugs[day.toordinal() % len(slugs)], lang)
