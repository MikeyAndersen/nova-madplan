from app.models import Recipe, RecipeCreate, ScrapePreview


def test_recipe_create_defaults():
    rc = RecipeCreate(title="Kødsovs")
    assert rc.ingredients == [] and rc.steps == [] and rc.source_url is None


def test_scrape_preview_shape():
    sp = ScrapePreview(parsed=RecipeCreate(title="X"), image_url=None, ok=True)
    assert sp.ok is True and sp.parsed.title == "X"


def test_recipe_has_image_flag():
    r = Recipe(id=1, title="X", ingredients=[], steps=[], tags=[],
              raw_snapshot="", has_image=True, source_url=None, time_min=None,
              created_at="t", updated_at="t")
    assert r.has_image is True
