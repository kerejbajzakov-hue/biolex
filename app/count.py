"""Print how many terms are in the dictionary.

Usage:  python -m app.count [--lang ru]
"""
from __future__ import annotations

import argparse

from . import db, repository as repo
from .seed import seed_if_empty


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lang", default="en", choices=["en", "kk", "ru"])
    args = p.parse_args()
    conn = db.connect()
    seed_if_empty(conn)
    s = repo.stats(conn, args.lang)
    print(f"Terms total: {s['total_terms']}   Themes: {s['total_themes']}")
    print("\nBy theme:")
    for t in s["by_theme"]:
        print(f"  {t['name']:<22} {t['term_count']:>4}")
    print("\nTranslated, by language:")
    for code, info in s["by_language"].items():
        print(f"  {code}  {info['name']:<10} {info['translated']:>4} / {s['total_terms']}")


if __name__ == "__main__":
    main()
