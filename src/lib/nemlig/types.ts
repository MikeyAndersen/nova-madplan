export interface ParsedItem {
  name: string;
  category: string; // nemlig-kategori, '' hvis ukendt (Format B)
  unit: string; // fx "1 l", "350 g", "4 stk."
  quantity: number; // heltal
  unitPrice?: number; // kr. pr. stk.
  discount?: number; // kr., valgfri
  total?: number; // kr. i alt for linjen
}

export interface ParsedRecipe {
  name: string;
  persons: number;
}

export interface ParseResult {
  items: ParsedItem[];
  recipes: ParsedRecipe[];
  unreadable: string[]; // linjer der ikke kunne læses
}
