from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db, dishes, weekplan


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="nova-madplan", lifespan=lifespan)
app.include_router(dishes.router)
app.include_router(weekplan.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
