import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import SEED_FILE

SEED = json.loads(SEED_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    with TestClient(create_app(db_path)) as c:
        yield c


def test_stats_counts_every_term(client):
    s = client.get("/api/stats").json()
    assert s["total_terms"] == len(SEED["terms"])
    assert sum(t["term_count"] for t in s["by_theme"]) == s["total_terms"]
    for code in ("en", "kk", "ru"):
        assert s["by_language"][code]["translated"] == s["total_terms"]


@pytest.mark.parametrize("lang,q,first", [
    ("en", "mito", "Mitochondrial DNA"),
    ("ru", "митох", "Митохондриальная ДНК"),
    ("kk", "митохондрия", "Митохондрия"),
])
def test_search_ranks_name_matches_first(client, lang, q, first):
    r = client.get("/api/terms", params={"lang": lang, "q": q}).json()
    assert r["total"] > 0
    assert r["items"][0]["name"] == first


def test_search_is_case_insensitive_for_cyrillic(client):
    a = client.get("/api/terms", params={"lang": "ru", "q": "ГЕН"}).json()["total"]
    b = client.get("/api/terms", params={"lang": "ru", "q": "ген"}).json()["total"]
    assert a == b > 0


def test_theme_filter_and_kazakh_alphabet(client):
    r = client.get("/api/terms", params={"lang": "kk", "theme": "genetics", "limit": 100}).json()
    assert all(i["theme"]["slug"] == "genetics" for i in r["items"])
    names = [i["name"] for i in r["items"]]
    assert names[0] == "Аллель"
    assert names.index("Гомозиготалы") < names.index("Доминантты аллель")


def test_term_detail_in_each_language(client):
    for lang, name in [("en", "Mitochondrion"), ("kk", "Митохондрия"), ("ru", "Митохондрия")]:
        t = client.get(f"/api/terms/mitochondrion?lang={lang}").json()
        assert t["name"] == name
        assert len(t["facts"]) == 3
        assert t["related"]


def test_unknown_term_and_bad_lang(client):
    assert client.get("/api/terms/nope").status_code == 404
    assert client.get("/api/terms?lang=de").status_code == 422


def test_batch_keeps_order(client):
    r = client.get("/api/terms/batch", params={"slugs": "gene,atp,missing"}).json()
    assert [i["slug"] for i in r] == ["gene", "atp"]


def test_today_and_frontend(client):
    assert client.get("/api/terms/today?lang=ru").status_code == 200
    assert "BioLex" in client.get("/").text


# ---------- user terms ----------

NEW_TERM = {
    "theme": "botany",
    "translations": {
        "ru": {"name": "Мой лишайник", "short_def": "Симбиоз гриба и водоросли.",
               "definition": "Длинное описание.", "facts": ["Растёт медленно", "  "]},
        "en": {"name": "", "short_def": ""},
    },
    "related": ["symbiosis"],
}


def test_create_edit_delete_user_term(client):
    before = client.get("/api/stats").json()["total_terms"]
    r = client.post("/api/terms?lang=ru", json=NEW_TERM)
    assert r.status_code == 201, r.text
    t = r.json()
    slug = t["slug"]
    assert t["custom"] and t["name"] == "Мой лишайник" and t["facts"] == ["Растёт медленно"]
    assert t["related"][0]["slug"] == "symbiosis"
    # shown in other languages too (falls back to the language it was written in)
    assert client.get(f"/api/terms/{slug}?lang=kk").json()["name"] == "Мой лишайник"
    # searchable and counted
    assert client.get("/api/terms", params={"lang": "en", "q": "лишайн"}).json()["items"][0]["slug"] == slug
    s = client.get("/api/stats").json()
    assert s["total_terms"] == before + 1 and s["custom_terms"] >= 1
    assert slug in [x["slug"] for x in client.get("/api/my-terms").json()]

    # edit: add an English version and change the theme
    body = {"theme": "ecology", "translations": {
        "ru": {"name": "Лишайник", "short_def": "Симбиоз гриба и водоросли."},
        "en": {"name": "Lichen", "short_def": "A partnership of a fungus and an alga."}}}
    r = client.put(f"/api/terms/{slug}?lang=en", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Lichen" and r.json()["theme"]["slug"] == "ecology"
    src = client.get(f"/api/terms/{slug}/source").json()
    assert set(src["translations"]) == {"ru", "en"}

    assert client.delete(f"/api/terms/{slug}").status_code == 204
    assert client.get(f"/api/terms/{slug}").status_code == 404


def test_user_term_validation_and_builtin_protection(client):
    bad = {"theme": "botany", "translations": {"ru": {"name": "Без определения", "short_def": ""}}}
    assert client.post("/api/terms", json=bad).status_code == 422
    assert client.post("/api/terms", json={"theme": "nope", "translations": {"en": {"name": "X", "short_def": "Y"}}}).status_code == 422
    assert client.put("/api/terms/mitochondrion", json=NEW_TERM).status_code == 403
    assert client.delete("/api/terms/mitochondrion").status_code == 403
