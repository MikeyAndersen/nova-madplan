"""Forslags-endpoints (INTEGRATION_SPEC §3.1)."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from . import config, db, suggest
from .auth import require_api_token
from .models import AcceptBody, SuggestionSet, WeekPlan
from .weekplan import apply_day_update, build_weekplan, monday_of, _now_iso, _parse_date

router = APIRouter(prefix="/api/suggestions", dependencies=[Depends(require_api_token)])


@router.get("/current", response_model=SuggestionSet)
def current() -> SuggestionSet:
    """Nyeste SuggestionSet (2.4) for næste uge; tomt sæt hvis intet er genereret."""
    ws = suggest.next_week_start()
    with db.connect() as conn:
        s = suggest.latest_set(conn, ws.isoformat())
    if s:
        return SuggestionSet(**s)
    return SuggestionSet(week_start=ws.isoformat(), generated_by=config.OLLAMA_MODEL,
                         quality="fast", inventory_hash=None, suggestions=[],
                         updated_at=_now_iso())


@router.post("/refresh", status_code=202)
async def refresh(bg: BackgroundTasks) -> dict:
    """Trig genberegning (7b) i baggrunden — returnerer straks 202 (§3.1)."""
    bg.add_task(suggest.generate, True)
    return {"status": "accepted", "week_start": suggest.next_week_start().isoformat()}


@router.post("/accept", response_model=WeekPlan)
def accept(body: AcceptBody) -> WeekPlan:
    """Skriv et forslag ind i ugeplanen som `planned` (§3.1)."""
    d = _parse_date(body.date)
    now = _now_iso()
    with db.connect() as conn:
        dish = conn.execute("SELECT id FROM dishes WHERE id = ?", (body.dish_id,)).fetchone()
        if not dish:
            raise HTTPException(status_code=404, detail=f"Dish {body.dish_id} not found")
        apply_day_update(conn, d, "planned", body.dish_id, None, now)
        return build_weekplan(conn, monday_of(d))
