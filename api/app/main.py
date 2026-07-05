import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from . import config, db, dishes, suggest, suggestions, weekplan

log = logging.getLogger("madplan")
scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if config.SUGGEST_AUTO:
        # Lager-poll: generate() genberegner kun hvis inventory_hash er ændret (§4.1).
        scheduler.add_job(suggest.generate, "interval",
                          minutes=config.INVENTORY_POLL_MINUTES, jitter=30)
        # Natligt kl. 03:00: tvungen genberegning (fanger last_made-drift, §4.1).
        scheduler.add_job(lambda: suggest.generate(force=True), CronTrigger(hour=3, minute=0))
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="nova-madplan", lifespan=lifespan)
app.include_router(dishes.router)
app.include_router(weekplan.router)
app.include_router(suggestions.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
