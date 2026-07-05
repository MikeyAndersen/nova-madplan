export type DayStatus = 'planned' | 'cooked' | 'skipped' | 'empty';

export interface Day {
	date: string;
	weekday: string;
	dish_id: number | null;
	dish_name: string | null;
	status: DayStatus;
	note: string | null;
}

export interface WeekPlan {
	week_start: string;
	days: Day[];
	updated_at: string;
}

export interface Ingredient {
	name: string;
	qty?: number | null;
	unit?: string | null;
}

export interface Dish {
	id: number;
	name: string;
	tags: string[];
	recurring_weekly: boolean;
	ingredients: Ingredient[];
	last_made: string | null;
	active: boolean;
}

export interface DishInput {
	name: string;
	tags?: string[];
	recurring_weekly?: boolean;
	ingredients?: Ingredient[];
	active?: boolean;
}

export interface Suggestion {
	date: string;
	dish_id: number;
	dish_name: string;
	reason: string;
	confidence: number;
}

export interface SuggestionSet {
	week_start: string;
	generated_by: string;
	quality: 'fast' | 'reviewed';
	inventory_hash: string | null;
	suggestions: Suggestion[];
	updated_at: string;
}
