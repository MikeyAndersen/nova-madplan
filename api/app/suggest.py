"""Forslags-motor (INTEGRATION_SPEC §4): deterministisk pre-filter + 7b-ranking.

Flow: hent lager (brain) → kandidater (14-dages-regel) → 7b rangerer → validér
mod kandidatlisten + genopfyld deterministisk → gem SuggestionSet (quality=fast)
+ kø-post til 32b (Fase 5). LLM-fejl er ikke fatalt: så står den deterministiske
rangering alene, og der genereres altid et sæt.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

import httpx

from . import config, db, inventory

log = logging.getLogger("madplan")

WEEKDAYS_DA = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]


def _tz() -> ZoneInfo:
    return ZoneInfo(config.TIMEZONE)


def _now_iso() -> str:
    return datetime.now(_tz()).isoformat(timespec="seconds")


def _today() -> date:
    return datetime.now(_tz()).date()


def next_week_start(today: date | None = None) -> date:
    """Forslag er altid for NÆSTE uge (§8.2). Uge = mandag."""
    today = today or _today()
    monday = today - timedelta(days=today.weekday())
    return monday + timedelta(days=7)


# ── Kandidater (§4.2 pre-filter + §4.3 14-dages-regel) ──────────────
def _days_since(last_made: str | None, today: date) -> int | None:
    if not last_made:
        return None
    try:
        return (today - date.fromisoformat(last_made)).days
    except ValueError:
        return None


def _eligible(dish: dict, today: date, threshold: int) -> bool:
    if dish["recurring_weekly"]:
        return True
    ds = _days_since(dish["last_made"], today)
    return ds is None or ds >= threshold


def load_active_dishes(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, tags, recurring_weekly, ingredients, last_made"
        " FROM dishes WHERE active = 1"
    ).fetchall()
    return [{
        "id": r["id"], "name": r["name"], "tags": json.loads(r["tags"]),
        "recurring_weekly": bool(r["recurring_weekly"]),
        "ingredients": json.loads(r["ingredients"]), "last_made": r["last_made"],
    } for r in rows]


def candidate_pool(dishes: list[dict], today: date) -> list[dict]:
    """Hård udelukkelse < 14 dage; falder kandidatmængden under 7, blødes op
    til < 7 dage (§4.3). recurring_weekly er altid med."""
    hard = [d for d in dishes if _eligible(d, today, config.SUGGEST_HARD_DAYS)]
    if len(hard) >= 7:
        return hard
    return [d for d in dishes if _eligible(d, today, config.SUGGEST_SOFT_DAYS)]


# ── Scoring mod lager (§4.2) ────────────────────────────────────────
def _bucket_weight(bucket: str | None) -> float:
    return 1.0 if bucket == "recently_done" else 0.6


def _ingredient_hit(name: str, inv: list[dict]) -> float:
    n = (name or "").strip().lower()
    if not n:
        return 0.0
    best = 0.0
    for item in inv:
        ratio = SequenceMatcher(None, n, (item.get("name") or "").lower()).ratio()
        if ratio >= config.FUZZY_RATIO:
            best = max(best, _bucket_weight(item.get("bucket")))
    return best


def coverage(dish: dict, inv: list[dict]) -> float:
    ings = dish.get("ingredients") or []
    if not ings:
        return 0.0
    return sum(_ingredient_hit(i.get("name", ""), inv) for i in ings) / len(ings)


def score(dish: dict, inv: list[dict], today: date) -> float:
    """0–1: lager-dækning primært, dage-siden sekundært, recurring lille bonus."""
    ds = _days_since(dish["last_made"], today)
    recency = 1.0 if ds is None else min(ds, 60) / 60
    base = 0.6 * coverage(dish, inv) + 0.4 * recency
    if dish["recurring_weekly"]:
        base += 0.2
    return round(min(base, 1.0), 3)


def _confidence(dish: dict, inv: list[dict], today: date) -> float:
    """Score, men sænket for blødt-optagne retter (< 14 dage, ikke recurring)."""
    conf = score(dish, inv, today)
    ds = _days_since(dish["last_made"], today)
    if not dish["recurring_weekly"] and ds is not None and ds < config.SUGGEST_HARD_DAYS:
        conf = round(conf * 0.7, 3)
    return conf


def _auto_reason(dish: dict, inv: list[dict], today: date) -> str:
    ds = _days_since(dish["last_made"], today)
    parts = []
    if coverage(dish, inv) > 0:
        parts.append("ingredienser på lager")
    if ds is None:
        parts.append("aldrig lavet før")
    else:
        parts.append(f"sidst lavet for {ds} dage siden")
    return "; ".join(parts).capitalize()


# ── 7b-ranking (Ollama) ─────────────────────────────────────────────
def _build_prompt(cands: list[dict], inv: list[dict], dates: list[str], today: date) -> str:
    cand_json = [{
        "dish_id": d["id"], "name": d["name"], "tags": d["tags"],
        "days_since": _days_since(d["last_made"], today),
        "recurring_weekly": d["recurring_weekly"],
        "coverage": round(coverage(d, inv), 2),
    } for d in cands]
    inv_json = [{"name": i.get("name"), "bucket": i.get("bucket")} for i in inv]
    return (
        "Du planlægger aftensmad for en dansk husstand for én uge.\n"
        "Vælg én ret pr. dag ud fra KANDIDATER (brug kun dish_id derfra).\n"
        "Vægt: ingredienser på lager, variation, og retter der ikke er lavet længe.\n"
        "Svar KUN med JSON: {\"suggestions\":[{\"date\":\"YYYY-MM-DD\",\"dish_id\":N,"
        "\"reason\":\"kort dansk begrundelse\",\"confidence\":0.0-1.0}]}\n\n"
        f"DATOER: {json.dumps(dates)}\n"
        f"KANDIDATER: {json.dumps(cand_json, ensure_ascii=False)}\n"
        f"LAGER: {json.dumps(inv_json, ensure_ascii=False)}\n"
    )


def _extract_suggestions(text: str) -> list[dict]:
    """Robust JSON-udtræk fra LLM-svar (kan være omkranset af tekst)."""
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return []
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return []
    if isinstance(data, list):
        return data
    return data.get("suggestions", []) if isinstance(data, dict) else []


async def rank_with_llm(cands: list[dict], inv: list[dict], dates: list[str],
                        today: date) -> list[dict]:
    """Kald 7b. Returnerer rå forslag (uvaliderede). Kaster ved fejl —
    kalderen falder tilbage til deterministisk rangering."""
    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": _build_prompt(cands, inv, dates, today),
        "stream": False, "format": "json",
        "options": {"temperature": 0.4},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(f"{config.OLLAMA_URL.rstrip('/')}/api/generate", json=payload)
        r.raise_for_status()
        return _extract_suggestions(r.json().get("response", ""))


# ── Validering + genopfyldning + samling af sættet ──────────────────
def assemble_set(week_start: date, pool: list[dict], inv: list[dict],
                 dates: list[str], raw: list[dict], today: date) -> dict:
    by_id = {d["id"]: d for d in pool}
    chosen: dict[str, dict] = {}
    used: set[int] = set()

    def place(dt: str, dish: dict, reason: str | None, conf: float | None) -> None:
        chosen[dt] = {
            "date": dt, "dish_id": dish["id"], "dish_name": dish["name"],
            "reason": reason or _auto_reason(dish, inv, today),
            "confidence": conf if conf is not None else _confidence(dish, inv, today),
        }
        used.add(dish["id"])

    # 1) LLM-forslag: kun gyldige dish_id fra kandidatlisten, unikke datoer/retter.
    for s in raw:
        dt, did = s.get("date"), s.get("dish_id")
        if dt in dates and dt not in chosen and did in by_id and did not in used:
            conf = s.get("confidence")
            try:
                conf = max(0.0, min(1.0, float(conf))) if conf is not None else None
            except (TypeError, ValueError):
                conf = None
            place(dt, by_id[did], s.get("reason"), conf)

    # 2) recurring_weekly garanteres en plads i ugen hvis muligt (§4.2).
    for dish in pool:
        if dish["recurring_weekly"] and dish["id"] not in used:
            slot = next((dt for dt in dates if dt not in chosen), None)
            if slot:
                place(slot, dish, None, None)

    # 3) genopfyld resterende dage deterministisk efter score (§4.2 validering).
    ranked = sorted((d for d in pool if d["id"] not in used),
                    key=lambda d: score(d, inv, today), reverse=True)
    it = iter(ranked)
    for dt in dates:
        if dt in chosen:
            continue
        dish = next(it, None)
        if dish is None:
            break  # færre end 7 kandidater — lad dagen stå tom
        place(dt, dish, None, None)

    return {
        "week_start": week_start.isoformat(),
        "generated_by": config.OLLAMA_MODEL,
        "quality": "fast",
        "inventory_hash": inventory.hash_inventory(inv),
        "suggestions": [chosen[dt] for dt in dates if dt in chosen],
        "updated_at": _now_iso(),
    }


# ── Persistens ──────────────────────────────────────────────────────
def latest_set(conn, week_start: str) -> dict | None:
    row = conn.execute(
        "SELECT payload_json FROM suggestion_sets WHERE week_start = ?"
        " ORDER BY id DESC LIMIT 1", (week_start,)
    ).fetchone()
    return json.loads(row["payload_json"]) if row else None


def save_set(conn, s: dict) -> None:
    payload = json.dumps(s, ensure_ascii=False)
    conn.execute(
        "INSERT INTO suggestion_sets(week_start, payload_json, quality, inventory_hash,"
        " generated_by, updated_at) VALUES(?,?,?,?,?,?)",
        (s["week_start"], payload, s["quality"], s["inventory_hash"],
         s["generated_by"], s["updated_at"]),
    )
    # Kø til 32b (Fase 5): idempotent pr. uge — nyeste pending vinder (§5).
    conn.execute("UPDATE suggest_queue SET status='expired'"
                 " WHERE week_start = ? AND status='pending'", (s["week_start"],))
    conn.execute("INSERT INTO suggest_queue(week_start, payload_json, status, created_at)"
                 " VALUES(?,?, 'pending', ?)", (s["week_start"], payload, _now_iso()))


# ── Orkestrering ────────────────────────────────────────────────────
async def generate(force: bool = False) -> dict | None:
    """Byg + gem et forslags-sæt for næste uge. force=False springer over hvis
    lageret (inventory_hash) er uændret siden sidste sæt (§4.1)."""
    week_start = next_week_start()
    try:
        inv = await inventory.fetch()
    except Exception:
        log.exception("inventory fetch failed — fortsætter uden lager")
        inv = []
    new_hash = inventory.hash_inventory(inv)

    with db.connect() as conn:
        prev = latest_set(conn, week_start.isoformat())
        if not force and prev and prev.get("inventory_hash") == new_hash:
            return None
        dishes = load_active_dishes(conn)

    today = _today()
    pool = candidate_pool(dishes, today)
    dates = [(week_start + timedelta(days=i)).isoformat() for i in range(7)]
    try:
        raw = await rank_with_llm(pool, inv, dates, today)
    except Exception:
        log.exception("7b-ranking fejlede — bruger deterministisk rangering")
        raw = []

    s = assemble_set(week_start, pool, inv, dates, raw, today)
    with db.connect() as conn:
        save_set(conn, s)
    return s
