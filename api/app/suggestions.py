"""Forslags-endpoints (INTEGRATION_SPEC §3.1)."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel

from . import config, db, suggest
from .auth import require_api_token
from .models import AcceptBody, SuggestionSet, WeekPlan
from .weekplan import apply_day_update, build_weekplan, monday_of, _now_iso, _parse_date

router = APIRouter(prefix="/api/suggestions", dependencies=[Depends(require_api_token)])


class RejectBody(BaseModel):
    dish_id: int


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
    """Skriv et forslag ind i ugeplanen som `planned` (§3.1). Rydder samtidig en
    evt. forkastelse af retten for den uge — mennesket ombestemte sig (Feature B)."""
    d = _parse_date(body.date)
    now = _now_iso()
    with db.connect() as conn:
        dish = conn.execute("SELECT id FROM dishes WHERE id = ?", (body.dish_id,)).fetchone()
        if not dish:
            raise HTTPException(status_code=404, detail=f"Dish {body.dish_id} not found")
        apply_day_update(conn, d, "planned", body.dish_id, None, now)
        conn.execute("DELETE FROM suggestion_rejections WHERE week_start = ? AND dish_id = ?",
                     (monday_of(d).isoformat(), body.dish_id))
        return build_weekplan(conn, monday_of(d))


@router.get("/rejections")
def get_rejections() -> dict:
    """Forkastede dish_id'er for næste uge (Feature B)."""
    ws = suggest.next_week_start().isoformat()
    with db.connect() as conn:
        return {"week_start": ws, "dish_ids": sorted(suggest.rejected_ids(conn, ws))}


@router.post("/reject", status_code=204)
def reject(body: RejectBody) -> Response:
    """Forkast en ret for næste uge — huskes til genberegning (Feature B)."""
    ws = suggest.next_week_start().isoformat()
    with db.connect() as conn:
        conn.execute("INSERT OR IGNORE INTO suggestion_rejections(week_start, dish_id, created_at)"
                     " VALUES(?,?,?)", (ws, body.dish_id, _now_iso()))
    return Response(status_code=204)


@router.post("/reject-all", status_code=202)
async def reject_all(bg: BackgroundTasks) -> dict:
    """Forkast alle retter i det aktuelle sæt og trig genberegning."""
    ws = suggest.next_week_start()
    now = _now_iso()
    with db.connect() as conn:
        s = suggest.latest_set(conn, ws.isoformat())
        for sug in (s.get("suggestions", []) if s else []):
            conn.execute("INSERT OR IGNORE INTO suggestion_rejections(week_start, dish_id, created_at)"
                         " VALUES(?,?,?)", (ws.isoformat(), sug["dish_id"], now))
    bg.add_task(suggest.generate, True)
    return {"status": "accepted", "week_start": ws.isoformat()}


@router.post("/reset-rejections", status_code=204)
def reset_rejections() -> Response:
    """Ryd ugens forkastede retter (Feature B)."""
    ws = suggest.next_week_start().isoformat()
    with db.connect() as conn:
        conn.execute("DELETE FROM suggestion_rejections WHERE week_start = ?", (ws,))
    return Response(status_code=204)
