// Data access: the Railway backend when configured, otherwise the bundled /dataset.json snapshot.

export type Terminal = { state: string; reason: string };

export type Attempt = { attempt: number; query: string; strategy: string; outcome: string; detail: string };

export type Ingredient = {
  index: number;
  raw: string;
  name: string;
  quantity: number | null;
  unit: string | null;
  status: "matched" | "unknown";
  food_id: string | null;
  food_description: string | null;
  grams: number | null;
  gram_basis: string | null;
  nutrition_status: string;
  nutrients: Record<string, number | null> | null;
  attempts: number;
  queries_tried: string[];
  attempt_log: Attempt[];
  unknown_reason: string | null;
};

export type Claim = { text: string; count: number; comment_ids: string[] };

export type RecipeRecord = {
  recipe_id: string;
  source_url: string;
  title: string;
  site: string;
  category: string[];
  yield_text: string | null;
  servings: number | null;
  servings_unit: string | null;
  provenance: { page_source: string; fetched_url: string; original_page_sha256: string; nutrition_source: string };
  ingredients: Ingredient[];
  match: { ingredients: number; matched: number; unknown: number; match_rate: number; retry_rounds: number; hit_retry_cap: number };
  nutrition: {
    complete: boolean;
    statement: string;
    totals: Record<string, number>;
    per_serving: Record<string, number> | null;
    ingredients_total: number;
    ingredients_with_nutrition: number;
  };
  cook_notes: {
    status: "produced" | "skipped_below_threshold";
    comment_count: number;
    threshold: number;
    claims: Claim[];
    card: string | null;
    word_count: number;
    backend: string | null;
  };
  terminal: Terminal;
  node_path: string[];
};

export type Row = {
  recipe_id: string;
  title: string;
  site: string;
  source_url: string;
  terminal: Terminal;
  matched: number;
  ingredients: number;
  nutrition_complete: boolean;
  with_nutrition: number;
  energy_kcal: number;
  card: boolean;
  comment_count: number;
};

export type Summary = {
  category: string;
  recipes: number;
  terminal_states: Record<string, number>;
  ingredients: number;
  matched: number;
  match_rate: number;
  ingredients_with_nutrition: number;
  unknown: number;
  hit_retry_cap: number;
  cards_produced: number;
  cards_skipped: number;
  retry_cap: number;
  comment_threshold: number;
  card_word_cap: number;
};

export type Config = {
  retry_cap: number;
  comment_threshold: number;
  card_word_cap: number;
  summariser: string;
  fetch_mode: string;
  handoff_configured: boolean;
  admin_configured: boolean;
};

export type Run = {
  run_id: string;
  url: string;
  status: "queued" | "running" | "done" | "error";
  node_path: string[];
  terminal?: Terminal;
  recipe_id?: string;
  error?: string;
};

const LS_BASE = "rra.apiBase";
const LS_TOKEN = "rra.adminToken";

function safeGet(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function safeSet(key: string, value: string) {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    /* storage unavailable: settings last for this page view only */
  }
}

export const settings = {
  apiBase(): string {
    return (safeGet(LS_BASE) || import.meta.env.VITE_API_BASE || "").replace(/\/+$/, "");
  },
  token(): string {
    return safeGet(LS_TOKEN);
  },
  save(apiBase: string, token: string) {
    safeSet(LS_BASE, apiBase.trim().replace(/\/+$/, ""));
    safeSet(LS_TOKEN, token.trim());
  },
};

let snapshot: Promise<{ recipes: RecipeRecord[]; retry_cap: number; comment_threshold: number; card_word_cap: number; category: string }> | null = null;

function loadSnapshot() {
  snapshot ??= fetch("/dataset.json").then((r) => r.json());
  return snapshot;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${settings.apiBase()}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${settings.apiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${settings.token()}` },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      msg += `: ${(await r.json()).detail ?? ""}`;
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return r.json();
}

function rowOf(r: RecipeRecord): Row {
  return {
    recipe_id: r.recipe_id,
    title: r.title,
    site: r.site,
    source_url: r.source_url,
    terminal: r.terminal,
    matched: r.match.matched,
    ingredients: r.match.ingredients,
    nutrition_complete: r.nutrition.complete,
    with_nutrition: r.nutrition.ingredients_with_nutrition,
    energy_kcal: r.nutrition.totals.energy_kcal,
    card: r.cook_notes.status === "produced",
    comment_count: r.cook_notes.comment_count,
  };
}

function summaryOf(ds: Awaited<ReturnType<typeof loadSnapshot>>): Summary {
  const ings = ds.recipes.flatMap((r) => r.ingredients);
  const matched = ings.filter((i) => i.status === "matched").length;
  const states: Record<string, number> = {};
  ds.recipes.forEach((r) => (states[r.terminal.state] = (states[r.terminal.state] ?? 0) + 1));
  return {
    category: ds.category,
    recipes: ds.recipes.length,
    terminal_states: states,
    ingredients: ings.length,
    matched,
    match_rate: ings.length ? matched / ings.length : 0,
    ingredients_with_nutrition: ings.filter((i) => i.nutrition_status === "computed").length,
    unknown: ings.length - matched,
    hit_retry_cap: ds.recipes.reduce((a, r) => a + r.match.hit_retry_cap, 0),
    cards_produced: ds.recipes.filter((r) => r.cook_notes.status === "produced").length,
    cards_skipped: ds.recipes.filter((r) => r.cook_notes.status !== "produced").length,
    retry_cap: ds.retry_cap,
    comment_threshold: ds.comment_threshold,
    card_word_cap: ds.card_word_cap,
  };
}

export const api = {
  live: () => Boolean(settings.apiBase()),

  async config(): Promise<Config | null> {
    return api.live() ? get<Config>("/api/config") : null;
  },
  async summary(): Promise<Summary> {
    return api.live() ? get<Summary>("/api/summary") : summaryOf(await loadSnapshot());
  },
  async recipes(): Promise<Row[]> {
    return api.live() ? get<Row[]>("/api/recipes") : (await loadSnapshot()).recipes.map(rowOf);
  },
  async recipe(id: string): Promise<RecipeRecord> {
    if (api.live()) return get<RecipeRecord>(`/api/recipes/${encodeURIComponent(id)}`);
    const r = (await loadSnapshot()).recipes.find((x) => x.recipe_id === id);
    if (!r) throw new Error("Recipe not found");
    return r;
  },
  pdfUrl: () => `${settings.apiBase()}/api/report.pdf`,
  startRun: (url: string) => post<Run>("/api/runs", { url }),
  run: (id: string) => get<Run>(`/api/runs/${id}`),
  startBatch: () => post<{ batch: string; run_ids: string[] }>("/api/batch"),
  handoff: () => post<{ status: number; n8n: string }>("/api/handoff"),
};
