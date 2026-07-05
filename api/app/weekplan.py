"""Ugeplan: opslag (spec 2.2) og dag-upsert. Uge = mandag-søndag (spec §8.2)."""
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from . import config, db, suggest
from .auth import require_api_token
from .models import Day, DayUpdate, WeekPlan

router = APIRouter(prefix="/api/weekplan", dependencies=[Depends(require_api_token)])

WEEKDAYS_DA = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]


def _tz() -> ZoneInfo:
    return ZoneInfo(config.TIMEZONE)


def _now_iso() -> str:
    return datetime.now(_tz()).isoformat(timespec="seconds")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid date: {value!r} (expected YYYY-MM-DD)")


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def build_weekplan(conn: sqlite3.Connection, week_start: date) -> WeekPlan:
    days: list[Day] = []
    latest_update: str | None = None
    for i in range(7):
        d = week_start + timedelta(days=i)
        row = conn.execute(
            "SELECT wd.dish_id, wd.status, wd.note, wd.updated_at, di.name AS dish_name"
            " FROM weekplan_days wd LEFT JOIN dishes di ON di.id = wd.dish_id"
            " WHERE wd.date = ?",
            (d.isoformat(),),
        ).fetchone()
        if row:
            days.append(Day(date=d.isoformat(), weekday=WEEKDAYS_DA[d.weekday()],
                            dish_id=row["dish_id"], dish_name=row["dish_name"],
                            status=row["status"], note=row["note"]))
            if latest_update is None or row["updated_at"] > latest_update:
                latest_update = row["updated_at"]
        else:
            days.append(Day(date=d.isoformat(), weekday=WEEKDAYS_DA[d.weekday()]))
    return WeekPlan(week_start=week_start.isoformat(), days=days,
                    updated_at=latest_update or _now_iso())


def _recompute_last_made(conn: sqlite3.Connection, dish_id: int) -> None:
    conn.execute(
        "UPDATE dishes SET last_made = (SELECT MAX(date) FROM history WHERE dish_id = ?),"
        " updated_at = ? WHERE id = ?",
        (dish_id, _now_iso(), dish_id),
    )


@router.get("/current", response_model=WeekPlan)
def get_current_weekplan() -> WeekPlan:
    today = datetime.now(_tz()).date()
    with db.connect() as conn:
        return build_weekplan(conn, monday_of(today))


@router.get("", response_model=WeekPlan)
def get_weekplan(start: str = Query(..., description="YYYY-MM-DD; rundes ned til mandag")) -> WeekPlan:
    week_start = monday_of(_parse_date(start))
    with db.connect() as conn:
        return build_weekplan(conn, week_start)


def apply_day_update(conn, d, status, dish_id, note, now) -> None:
    """Kernen bag PUT /day og forslags-accept: upsert dagen og hold historik +
    last_made i sync med cooked-status. Antager dish_id allerede er valideret."""
    old = conn.execute("SELECT dish_id FROM history WHERE date = ?", (d.isoformat(),)).fetchone()
    conn.execute(
        "INSERT INTO weekplan_days(date, dish_id, status, note, updated_at)"
        " VALUES(?,?,?,?,?) ON CONFLICT(date) DO UPDATE SET"
        " dish_id=excluded.dish_id, status=excluded.status,"
        " note=excluded.note, updated_at=excluded.updated_at",
        (d.isoformat(), dish_id, status, note, now),
    )
    # Historik holdes 1:1 med cooked-status for datoen; last_made følger historikken.
    conn.execute("DELETE FROM history WHERE date = ?", (d.isoformat(),))
    if status == "cooked":
        conn.execute("INSERT INTO history(date, dish_id, cooked_at) VALUES(?,?,?)",
                     (d.isoformat(), dish_id, now))
    for did in {dish_id, old["dish_id"] if old else None} - {None}:
        _recompute_last_made(conn, did)


@router.put("/day", response_model=WeekPlan)
def upsert_day(update: DayUpdate, bg: BackgroundTasks) -> WeekPlan:
    """Sæt/ret én dag. `cooked` skriver historik og opdaterer `last_made` (spec 2.2)."""
    d = _parse_date(update.date)
    if update.status == "empty":
        if update.dish_id is not None:
            raise HTTPException(status_code=422, detail="dish_id must be null when status is 'empty'")
    elif update.dish_id is None:
        raise HTTPException(status_code=422, detail=f"dish_id is required when status is {update.status!r}")

    now = _now_iso()
    with db.connect() as conn:
        if update.dish_id is not None:
            dish = conn.execute("SELECT id FROM dishes WHERE id = ?", (update.dish_id,)).fetchone()
            if not dish:
                raise HTTPException(status_code=404, detail=f"Dish {update.dish_id} not found")
        apply_day_update(conn, d, update.status, update.dish_id, update.note, now)
        plan = build_weekplan(conn, monday_of(d))
    # Cooked/skipped ændrer historik/last_made → genberegn næste uges forslag (§4.1).
    if config.SUGGEST_AUTO and update.status in ("cooked", "skipped"):
        bg.add_task(suggest.generate, True)
    return plan
