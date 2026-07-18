"""Statistik (Feature D): antal-lavet pr. ret + måltider pr. måned, fra history.
Deles med den smarte ret-vælger (frekvens-rangering, Feature A)."""
from fastapi import APIRouter, Depends

from . import db
from .auth import require_api_token
from .models import DishStat, MonthCount, StatsResponse

router = APIRouter(prefix="/api/stats", dependencies=[Depends(require_api_token)])


@router.get("", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    with db.connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM history").fetchone()["n"]
        dish_rows = conn.execute(
            "SELECT h.dish_id, di.name AS name, COUNT(*) AS times_made,"
            " MAX(h.date) AS last_made"
            " FROM history h JOIN dishes di ON di.id = h.dish_id"
            " GROUP BY h.dish_id, di.name"
            " ORDER BY times_made DESC, di.name COLLATE NOCASE"
        ).fetchall()
        month_rows = conn.execute(
            "SELECT substr(date, 1, 7) AS month, COUNT(*) AS count"
            " FROM history GROUP BY month ORDER BY month"
        ).fetchall()
    return StatsResponse(
        total_cooked=total,
        dishes=[DishStat(dish_id=r["dish_id"], name=r["name"],
                         times_made=r["times_made"], last_made=r["last_made"])
                for r in dish_rows],
        per_month=[MonthCount(month=r["month"], count=r["count"]) for r in month_rows],
    )
