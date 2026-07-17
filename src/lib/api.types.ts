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
	recipe_id?: number | null;
}

export interface DishInput {
	name: string;
	tags?: string[];
	recurring_weekly?: boolean;
	ingredients?: Ingredient[];
	active?: boolean;
	recipe_id?: number | null;
}

export interface Recipe {
	id: number;
	title: string;
	source_url: string | null;
	ingredients: Ingredient[];
	steps: string[];
	time_min: number | null;
	tags: string[];
	raw_snapshot: string;
	has_image: boolean;
	created_at: string;
	updated_at: string;
}

export interface RecipeInput {
	title: string;
	source_url?: string | null;
	ingredients?: Ingredient[];
	steps?: string[];
	time_min?: number | null;
	tags?: string[];
	raw_snapshot?: string;
	image_url?: string | null;
}

export interface ScrapePreview {
	parsed: Omit<RecipeInput, 'image_url'>;
	image_url: string | null;
	ok: boolean;
	warning?: string;
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

export interface InventoryItem {
	id: number;
	name: string;
	name_key: string;
	quantity: number;
	unit: string | null;
	note: string | null;
	category: string | null;
	source: string;
	added_at: string;
	updated_at: string;
}

export interface InventoryItemInput {
	name: string;
	quantity?: number;
	unit?: string | null;
	note?: string | null;
	category?: string | null;
	source?: string;
}
