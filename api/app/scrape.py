"""Recipe-scraping: netværks-fetch adskilt fra ren parsing (så tests er
netværksfri). parse_recipe fejler blødt — returnerer altid et snapshot og
en ikke-tom titel, selv når der ikke er strukturerede data."""
import re
from urllib.parse import urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
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


# ── Mængde-kvalitet + headless fallback (§ scrape-amounts) ──────────
_AMOUNT_IN_TEXT = re.compile(r"[\d½¼¾⅓⅔]")
# En "ingredient-linje" starter typisk med en mængde: tal eller enhed.
_QTY_START = re.compile(
    r"^\s*(?:[\d½¼¾⅓⅔]|(?:g|kg|dl|ml|l|stk|spsk|tsk|fed|bæger|dåse|knsp|drys|kvist|håndfuld|lille|stort?)\b)",
    re.IGNORECASE)


def ingredients_have_amounts(ings, threshold: float = 0.34) -> bool:
    """True hvis en rimelig andel af ingredienserne indeholder en mængde (tal/brøk).
    nemlig o.l. giver navne uden mængder → False → trig headless fallback."""
    names = [(i.name if hasattr(i, "name") else i.get("name", "")) for i in ings]
    names = [n for n in names if n]
    if not names:
        return False
    with_amt = sum(1 for n in names if _AMOUNT_IN_TEXT.search(n))
    return with_amt / len(names) >= threshold


def extract_dom_ingredients(html: str) -> list[str]:
    """Træk ingrediens-linjer (med mængder) fra renderet DOM. Vælger den container
    med flest mængde-startende linjer og returnerer dem i dokument-rækkefølge —
    virker på tværs af undergrupper (fx nemligs 'Topping'). Site-agnostisk heuristik."""
    soup = BeautifulSoup(html, "html.parser")

    def line_text(el) -> str:
        return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()

    qualifying = []
    for el in soup.find_all(["li", "tr"]):
        t = line_text(el)
        if t and len(t) <= 120 and _QTY_START.match(t):
            qualifying.append(el)

    best, best_count, best_size = None, 0, float("inf")
    seen_containers = {}
    for el in qualifying:
        for anc in el.parents:
            if getattr(anc, "name", None) in ("table", "ul", "ol", "div", "section"):
                seen_containers[id(anc)] = anc
    for anc in seen_containers.values():
        lines = [el for el in qualifying if anc in el.parents]
        size = len(anc.get_text())
        if len(lines) > best_count or (len(lines) == best_count and size < best_size):
            best, best_count, best_size = anc, len(lines), size

    if not best or best_count < 3:
        return []
    out, seen = [], set()
    for el in qualifying:
        if best in el.parents:
            t = line_text(el)
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def fetch_html_rendered(url: str) -> str:
    """Renderet HTML via headless Chromium (Playwright). Lazy import så modulet
    kan indlæses uden playwright installeret. Bruges kun som fallback."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(user_agent=_UA)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)  # lad klient-JS hydrere mængderne
            return page.content()
        finally:
            browser.close()


def scrape_recipe_smart(url: str) -> ScrapePreview:
    """Hurtig sti (httpx) først; kun hvis mængder mangler, spin headless op og
    træk ingredienserne fra den renderede DOM. Fejler blødt til et flag."""
    html = fetch_html(url)          # kan raise → endpoint svarer 502
    prev = parse_recipe(html, url)
    if ingredients_have_amounts(prev.parsed.ingredients):
        return prev
    try:
        rendered = fetch_html_rendered(url)
        dom = extract_dom_ingredients(rendered)
        if dom and ingredients_have_amounts([Ingredient(name=x) for x in dom]):
            prev.parsed.ingredients = [Ingredient(name=x) for x in dom]
            snap = extract_snapshot(rendered)
            if snap:
                prev.parsed.raw_snapshot = snap
            prev.ok = True
            prev.warning = None
            return prev
    except Exception:
        pass
    if prev.parsed.ingredients:
        prev.ok = False
        prev.warning = "⚠️ Mængder mangler — tjek og udfyld dem selv."
    return prev
