# BioLex — biology dictionary (EN / ҚАЗ / РУС)

A trilingual biology dictionary: **SQLite** database, **Python FastAPI** backend, and a web app
in the BioLex design (claymorphism illustrations, glass and neumorphic UI, lime `#A7FC00` + violet `#6600FF`).

The seed dictionary has **156 terms in 6 themes**, each translated into all 3 languages.

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- App: http://127.0.0.1:8000
- API docs (Swagger): http://127.0.0.1:8000/docs

On first start the database `biolex.db` is created and filled from `data/seed.json` automatically.

## Count the terms

```bash
python -m app.count            # English names
python -m app.count --lang ru  # theme names in Russian
```

The same numbers are shown in the app (home screen, theme tiles, Stats tab) and via `GET /api/stats`.

## Architecture

```
static/  (HTML + CSS + JS, no build step)
   │  fetch /api/...
   ▼
app/main.py         FastAPI routes, validation, serves static/
app/repository.py   all SQL: search, counts, term-of-the-day, alphabet sorting
app/schemas.py      Pydantic response models (shown in /docs)
app/db.py           SQLite connection + schema
app/seed.py         loads data/seed.json → SQLite (idempotent upsert)
   ▼
biolex.db (SQLite)
```

### Database (SQLite)

| table | purpose |
|---|---|
| `languages` | en, kk, ru |
| `themes` / `theme_translations` | 6 themes, name + description per language |
| `terms` | one row per term (slug, theme) |
| `term_translations` | name, short definition, full definition, pronunciation, grammar, etymology — per language; `*_norm` columns hold casefolded text so Cyrillic search is case-insensitive |
| `term_facts` | "key facts" bullet points per language |
| `term_relations` | related terms |

Missing translations fall back to English automatically.

### API

| method | path | what it returns |
|---|---|---|
| GET | `/api/stats?lang=` | total terms, terms per theme, translated terms per language |
| GET | `/api/themes?lang=` | themes with term counts |
| GET | `/api/themes/{slug}?lang=` | one theme |
| GET | `/api/terms?lang=&q=&theme=&limit=&offset=` | search (name matches ranked first, sorted by each language's alphabet) |
| GET | `/api/terms/{slug}?lang=` | full article with facts and related terms |
| GET | `/api/terms/today?lang=` | term of the day |
| GET | `/api/terms/batch?slugs=a,b` | several terms (used by Saved) |
| POST | `/api/terms` | add your own term (one, two or all three languages) |
| GET | `/api/terms/{slug}/source` | all languages of a term as entered (edit form) |
| PUT | `/api/terms/{slug}` | edit your own term (built-in terms are read-only → 403) |
| DELETE | `/api/terms/{slug}` | delete your own term |
| GET | `/api/my-terms?lang=` | the terms users added |

`lang` is `en`, `kk` or `ru`.

## Adding terms

Add entries to `data/seed.json` (or a separate file with the same shape) and run:

```bash
python -m app.seed                    # updates existing slugs, adds new ones
python -m app.seed --file new.json    # load another file
python -m app.seed --reset            # rebuild the database from scratch
```

Minimal term entry:

```json
{
  "slug": "nucleus",
  "theme": "cell-biology",
  "name":  {"en": "Nucleus", "kk": "Ядро", "ru": "Ядро"},
  "short": {"en": "…", "kk": "…", "ru": "…"}
}
```

Optional fields: `definition`, `pronunciation`, `grammar`, `etymology` (each `{en, kk, ru}`),
`facts` (`{"en": ["…"], …}`) and `related` (list of slugs).

## Website on GitHub Pages (github.io)

`docs/` holds a static build of the app for `https://<user>.github.io/biolex/`. GitHub Pages has no
Python server, so the site uses `static/js/localapi.js`, which answers the same API in the browser
from `data/seed.json`.

One-time setup: **Settings → Pages → Build and deployment → Source: Deploy from a branch → `main` / `/docs` → Save**.

After changing the app or the terms, rebuild and push: `python tools/build_pages.py` (writes `docs/`).

## Tests

```bash
pip install pytest httpx
pytest
```

## App features

- Language switch ENG / ҚАЗ / РУС on every main screen (remembered on the device)
- Live search with theme filters
- Term page: pronunciation (spoken with the browser's speech engine), definition, key facts, word origin, related terms
- Themes with A–Z lists in each language's own alphabet (Kazakh letters Ә, Қ, Ң… in their real place)
- **Your own terms:** add a term with a theme, short definition, full description, pronunciation, key facts and word origin —
  in one language or all three; edit or delete it later. They appear in search, themes and stats like built-in terms.
  With the FastAPI server they are stored in SQLite (`terms.is_custom = 1`); on GitHub Pages they are stored in the browser.
- Saved terms (stored on the device), Stats tab with term counts
- Works on phones and installs as a web app (manifest included)
