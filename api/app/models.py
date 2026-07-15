"""Pydantic-modeller — feltnavne følger datakontrakterne i INTEGRATION_SPEC §2 præcist."""
from typing import Literal

from pydantic import BaseModel, Field

DayStatus = Literal["planned", "cooked", "skipped", "empty"]


class Ingredient(BaseModel):
    name: str
    qty: float | None = None
    unit: str | None = None


class Dish(BaseModel):
    id: int
    name: str
    tags: list[str] = []
    recurring_weekly: bool = False
    ingredients: list[Ingredient] = []
    last_made: str | None = None
    active: bool = True


class DishCreate(BaseModel):
    name: str = Field(min_length=1)
    tags: list[str] = []
    recurring_weekly: bool = False
    ingredients: list[Ingredient] = []
    active: bool = True


class DishUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    recurring_weekly: bool | None = None
    ingredients: list[Ingredient] | None = None
    active: bool | None = None


class Day(BaseModel):
    date: str
    weekday: str
    dish_id: int | None = None
    dish_name: str | None = None
    status: DayStatus = "empty"
    note: str | None = None


class WeekPlan(BaseModel):
    week_start: str
    days: list[Day]
    updated_at: str


class DayUpdate(BaseModel):
    date: str  # YYYY-MM-DD
    status: DayStatus
    dish_id: int | None = None
    note: str | None = None


# ── Forslag (spec §2.4) ─────────────────────────────────────────────
class Suggestion(BaseModel):
    date: str
    dish_id: int
    dish_name: str
    reason: str
    confidence: float


class SuggestionSet(BaseModel):
    week_start: str
    generated_by: str
    quality: Literal["fast", "reviewed"] = "fast"
    inventory_hash: str | None = None
    suggestions: list[Suggestion] = []
    updated_at: str


class AcceptBody(BaseModel):
    date: str  # YYYY-MM-DD
    dish_id: int


# ── Beholdning (Feature B, spec §4.1) ───────────────────────────────
class InventoryItemIn(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = 1
    unit: str | None = None
    note: str | None = None
    category: str | None = None   # frontendens lokations-slug (koleskab|fryser|skab|ovrigt)
    source: str = "manuel"        # nemlig | manuel


class InventoryBulkIn(BaseModel):
    items: list[InventoryItemIn]
    merge: bool = True            # merge-på-navn: læg quantity til eksisterende (§8)


class InventoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    quantity: float | None = None
    unit: str | None = None
    note: str | None = None
    category: str | None = None


class InventoryItem(InventoryItemIn):
    id: int
    name_key: str
    added_at: str
    updated_at: str
