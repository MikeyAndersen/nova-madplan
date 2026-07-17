import pathlib

from app import scrape

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_parse_structured_recipe():
    sp = scrape.parse_recipe(_read("recipe_jsonld.html"), "https://example.com/r")
    assert sp.ok is True
    assert sp.parsed.title == "Kødsovs"
    assert len(sp.parsed.ingredients) == 3
    assert sp.parsed.ingredients[0].name == "500 g hakket oksekød"
    assert len(sp.parsed.steps) == 2
    assert sp.parsed.time_min == 45
    assert sp.image_url == "https://example.com/kodsovs.jpg"
    assert sp.parsed.raw_snapshot  # snapshot always present


def test_parse_plain_page_fails_soft():
    sp = scrape.parse_recipe(_read("plain.html"), "https://example.com/note")
    assert sp.ok is False
    assert sp.warning  # tells the user to fill fields in
    assert sp.parsed.raw_snapshot  # snapshot still captured
    assert sp.parsed.title  # falls back to <title> or url, never empty


def test_extract_snapshot_returns_text():
    text = scrape.extract_snapshot(_read("plain.html"))
    assert "frikadeller" in text.lower()
