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
