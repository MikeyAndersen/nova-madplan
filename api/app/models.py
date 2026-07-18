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
    recipe_id: int | None = None


class DishCreate(BaseModel):
    name: str = Field(min_length=1)
    tags: list[str] = []
    recurring_weekly: bool = False
    ingredients: list[Ingredient] = []
    active: bool = True
    recipe_id: int | None = None


class DishUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    recurring_weekly: bool | None = None
    ingredients: list[Ingredient] | None = None
    active: bool | None = None
    recipe_id: int | None = None


class Day(BaseModel):
    date: str
    weekday: str
    dish_id: int | None = None
    dish_name: str | None = None
    recipe_id: int | None = None
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


# ── Opskrifter ──────────────────────────────────────────────────────
class RecipeCreate(BaseModel):
    title: str = Field(min_length=1)
    source_url: str | None = None
    ingredients: list[Ingredient] = []
    steps: list[str] = []
    time_min: int | None = None
    tags: list[str] = []
    raw_snapshot: str = ""


class RecipeInput(RecipeCreate):
    """Alias for readability at call sites; identical shape to RecipeCreate."""


class RecipePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    source_url: str | None = None
    ingredients: list[Ingredient] | None = None
    steps: list[str] | None = None
    time_min: int | None = None
    tags: list[str] | None = None
    raw_snapshot: str | None = None


class Recipe(RecipeCreate):
    id: int
    has_image: bool = False
    created_at: str
    updated_at: str


class ScrapePreview(BaseModel):
    parsed: RecipeCreate
    image_url: str | None = None
    ok: bool = True
    warning: str | None = None


# ── Statistik (Feature D) ───────────────────────────────────────────
class DishStat(BaseModel):
    dish_id: int
    name: str
    times_made: int
    last_made: str | None = None


class MonthCount(BaseModel):
    month: str
    count: int


class StatsResponse(BaseModel):
    total_cooked: int
    dishes: list[DishStat] = []
    per_month: list[MonthCount] = []
