"""Recipe-scraping: netværks-fetch adskilt fra ren parsing (så tests er
netværksfri). parse_recipe fejler blødt — returnerer altid et snapshot og
en ikke-tom titel, selv når der ikke er strukturerede data."""
import re
from urllib.parse import urlparse

import httpx
import trafilatura
from recipe_scrapers import scrape_html

from .models import Ingredient, RecipeCreate, ScrapePreview

_UA = "Mozilla/5.0 (compatible; nova-madplan/1.0; +https://madplan.nova-tech.dk)"
_TIMEOUT = httpx.Timeout(15.0)


def fetch_html(url: str) -> str:
    r = httpx.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT,
                  follow_redirects=True)
    r.raise_for_status()
    return r.text


def fetch_image(url: str) -> tuple[bytes, str] | None:
    try:
        r = httpx.get(url, headers={"User-Agent": _UA}, timeout=_TIMEOUT,
                      follow_redirects=True)
        r.raise_for_status()
    except Exception:
        return None
    mime = r.headers.get("content-type", "").split(";")[0].strip()
    if not mime.startswith("image/") or not r.content:
        return None
    return r.content, mime


def extract_snapshot(html: str) -> str:
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    return text or ""


def _title_from_html(html: str, url: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return urlparse(url).netloc or "Ny opskrift"


def parse_recipe(html: str, url: str) -> ScrapePreview:
    snapshot = extract_snapshot(html)
    try:
        s = scrape_html(html, org_url=url, supported_only=False)
        title = (s.title() or "").strip()
        ingredients = [Ingredient(name=i.strip()) for i in (s.ingredients() or []) if i.strip()]
        steps = [x.strip() for x in (s.instructions_list() or []) if x.strip()]
        try:
            total = s.total_time()
            time_min = int(total) if total else None
        except Exception:
            time_min = None
        try:
            image_url = s.image() or None
        except Exception:
            image_url = None
        if title and (ingredients or steps):
            return ScrapePreview(
                parsed=RecipeCreate(title=title, source_url=url, ingredients=ingredients,
                                    steps=steps, time_min=time_min, raw_snapshot=snapshot),
                image_url=image_url, ok=True)
    except Exception:
        pass
    # fail-soft: intet struktureret — behold snapshot + gæt titel
    return ScrapePreview(
        parsed=RecipeCreate(title=_title_from_html(html, url), source_url=url,
                            raw_snapshot=snapshot),
        image_url=None, ok=False,
        warning="Kunne ikke læse strukturerede data — udfyld felterne selv (teksten er gemt).")
