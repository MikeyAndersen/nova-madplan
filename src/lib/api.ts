import type { WeekPlan, Dish, DishInput, SuggestionSet, DayStatus, InventoryItem, InventoryItemInput, Recipe, RecipeInput, ScrapePreview, Stats } from './api.types';
export type * from './api.types';

export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string,
	) {
		super(`API ${status}: ${detail}`);
		this.name = 'ApiError';
	}
}

export function makeApi(base: string, token: string, fetchImpl: typeof fetch = fetch) {
	const root = base.replace(/\/$/, '');
	async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
		const res = await fetchImpl(`${root}${path}`, {
			...init,
			headers: {
				Authorization: `Bearer ${token}`,
				...(init.body ? { 'content-type': 'application/json' } : {}),
				...(init.headers ?? {}),
			},
		});
		if (!res.ok) {
			let detail = res.statusText;
			try {
				detail = ((await res.json()) as { detail?: string }).detail ?? detail;
			} catch {
				/* non-JSON body */
			}
			throw new ApiError(res.status, detail);
		}
		if (res.status === 204) return undefined as T;
		return (await res.json()) as T;
	}

	return {
		getCurrentWeekplan: () => call<WeekPlan>('/api/weekplan/current'),
		getWeekplan: (start: string) => call<WeekPlan>(`/api/weekplan?start=${encodeURIComponent(start)}`),
		putDay: (b: { date: string; status: DayStatus; dish_id: number | null; note: string | null }) =>
			call<WeekPlan>('/api/weekplan/day', { method: 'PUT', body: JSON.stringify(b) }),
		listDishes: (includeInactive = true) => call<Dish[]>(`/api/dishes?include_inactive=${includeInactive}`),
		createDish: (b: DishInput) => call<Dish>('/api/dishes', { method: 'POST', body: JSON.stringify(b) }),
		updateDish: (id: number, b: Partial<DishInput>) =>
			call<Dish>(`/api/dishes/${id}`, { method: 'PUT', body: JSON.stringify(b) }),
		deleteDish: (id: number) => call<void>(`/api/dishes/${id}`, { method: 'DELETE' }),
		getSuggestions: () => call<SuggestionSet>('/api/suggestions/current'),
		refreshSuggestions: () => call<void>('/api/suggestions/refresh', { method: 'POST' }),
		acceptSuggestion: (date: string, dish_id: number) =>
			call<WeekPlan>('/api/suggestions/accept', { method: 'POST', body: JSON.stringify({ date, dish_id }) }),
		getRejections: () => call<{ week_start: string; dish_ids: number[] }>('/api/suggestions/rejections'),
		rejectSuggestion: (dish_id: number) =>
			call<void>('/api/suggestions/reject', { method: 'POST', body: JSON.stringify({ dish_id }) }),
		rejectAllSuggestions: () => call<void>('/api/suggestions/reject-all', { method: 'POST' }),
		resetRejections: () => call<void>('/api/suggestions/reset-rejections', { method: 'POST' }),
		listInventory: (filter: { q?: string; category?: string } = {}) => {
			const p = new URLSearchParams();
			if (filter.q) p.set('q', filter.q);
			if (filter.category) p.set('category', filter.category);
			const qs = p.toString();
			return call<InventoryItem[]>(`/api/inventory${qs ? `?${qs}` : ''}`);
		},
		bulkAddInventory: (items: InventoryItemInput[], merge = true) =>
			call<{ added: number; merged: number }>('/api/inventory', {
				method: 'POST',
				body: JSON.stringify({ items, merge }),
			}),
		updateInventoryItem: (id: number, patch: Partial<InventoryItemInput>) =>
			call<InventoryItem>(`/api/inventory/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
		deleteInventoryItem: (id: number) => call<void>(`/api/inventory/${id}`, { method: 'DELETE' }),
		scrapeRecipe: (url: string) =>
			call<ScrapePreview>('/api/recipes/scrape', { method: 'POST', body: JSON.stringify({ url }) }),
		listRecipes: (q?: string) =>
			call<Recipe[]>(`/api/recipes${q ? `?q=${encodeURIComponent(q)}` : ''}`),
		getRecipe: (id: number) => call<Recipe>(`/api/recipes/${id}`),
		createRecipe: (b: RecipeInput) =>
			call<Recipe>('/api/recipes', { method: 'POST', body: JSON.stringify(b) }),
		updateRecipe: (id: number, b: Partial<RecipeInput>) =>
			call<Recipe>(`/api/recipes/${id}`, { method: 'PATCH', body: JSON.stringify(b) }),
		deleteRecipe: (id: number) => call<void>(`/api/recipes/${id}`, { method: 'DELETE' }),
		getStats: () => call<Stats>('/api/stats'),
	};
}

export async function getApi() {
	const { env } = await import('cloudflare:workers');
	return makeApi(env.MADPLAN_API_BASE, env.LIFEHUB_API_TOKEN);
}
