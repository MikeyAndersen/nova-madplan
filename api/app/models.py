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
