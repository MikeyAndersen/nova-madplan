import pathlib

from app import scrape
from app.models import Ingredient

FIX = pathlib.Path(__file__).parent / "fixtures"


def _read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_ingredients_have_amounts_detects_names_only():
    names_only = [Ingredient(name="Pasta"), Ingredient(name="Løg"), Ingredient(name="Hvidløg")]
    with_amt = [Ingredient(name="500 g pasta"), Ingredient(name="2 fed hvidløg"), Ingredient(name="salt")]
    assert scrape.ingredients_have_amounts(names_only) is False
    assert scrape.ingredients_have_amounts(with_amt) is True
    assert scrape.ingredients_have_amounts([]) is False


def test_extract_dom_ingredients_pairs_amount_and_name_across_groups():
    lines = scrape.extract_dom_ingredients(_read("nemlig_rendered.html"))
    assert "500 g Pasta (gerne rigatoni)" in lines
    assert "2 fed Hvidløg" in lines
    assert "20 g Parmesan" in lines          # second group included
    assert "Cremet pasta med salsiccia" not in lines   # header excluded
    assert len(lines) == 6


def test_smart_falls_back_to_render_when_amounts_missing(monkeypatch):
    names_only_html = _read("recipe_jsonld.html").replace(
        '"500 g hakket oksekød","1 løg","2 dåser flåede tomater"', '"oksekød","løg","tomater"')
    monkeypatch.setattr(scrape, "fetch_html", lambda url: names_only_html)
    monkeypatch.setattr(scrape, "fetch_html_rendered", lambda url: _read("nemlig_rendered.html"))
    prev = scrape.scrape_recipe_smart("https://x/r")
    assert prev.ok is True
    joined = " ".join(i.name for i in prev.parsed.ingredients)
    assert "500 g" in joined and "Parmesan" in joined
    assert prev.warning is None


def test_smart_flags_when_render_unavailable(monkeypatch):
    names_only_html = _read("recipe_jsonld.html").replace(
        '"500 g hakket oksekød","1 løg","2 dåser flåede tomater"', '"oksekød","løg","tomater"')
    monkeypatch.setattr(scrape, "fetch_html", lambda url: names_only_html)
    def boom(url):
        raise RuntimeError("no browser")
    monkeypatch.setattr(scrape, "fetch_html_rendered", boom)
    prev = scrape.scrape_recipe_smart("https://x/r")
    assert prev.ok is False
    assert "Mængder mangler" in (prev.warning or "")


def test_smart_skips_render_when_amounts_present(monkeypatch):
    monkeypatch.setattr(scrape, "fetch_html", lambda url: _read("recipe_jsonld.html"))
    def should_not_call(url):
        raise AssertionError("render should not run when amounts already present")
    monkeypatch.setattr(scrape, "fetch_html_rendered", should_not_call)
    prev = scrape.scrape_recipe_smart("https://x/r")
    assert prev.ok is True
    assert scrape.ingredients_have_amounts(prev.parsed.ingredients)
