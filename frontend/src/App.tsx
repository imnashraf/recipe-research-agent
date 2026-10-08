import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { api, settings, type Config, type RecipeRecord, type Row, type Run, type Summary } from "./api";

const NODE_ORDER = ["fetch", "parse_recipe", "parse_ingredients", "match_nutrition", "mark_unknown", "gather_comments", "summarise", "validate", "write"];

function useHashRoute(): string {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash;
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const n0 = (x: number | null | undefined) => (x == null ? "–" : Math.round(x).toLocaleString());

function StatePill({ state }: { state: string }) {
  return <span className={`pill pill-${state}`}>{state.replace(/_/g, " ")}</span>;
}

// ------------------------------------------------------------------------------------ settings
function SettingsPanel({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [base, setBase] = useState(settings.apiBase());
  const [token, setToken] = useState(settings.token());
  return (
    <div className="panel settings">
      <h2>Connection</h2>
      <label>
        Backend URL (Railway)
        <input value={base} onChange={(e) => setBase(e.target.value)} placeholder="https://your-service.up.railway.app" />
      </label>
      <label>
        Admin token <span className="muted">(only needed to run recipes or send for approval; kept in this browser)</span>
        <input value={token} onChange={(e) => setToken(e.target.value)} type="password" autoComplete="off" />
      </label>
      <div className="row">
        <button
          className="primary"
          onClick={() => {
            settings.save(base, token);
            onSaved();
            onClose();
          }}
        >
          Save
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------ run panel
function RunPanel({ config, onFinished }: { config: Config | null; onFinished: () => void }) {
  const [url, setUrl] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const live = api.live();
  const canAdmin = live && Boolean(settings.token());

  useEffect(() => {
    if (!run || run.status === "done" || run.status === "error") return;
    const t = setInterval(async () => {
      try {
        const r = await api.run(run.run_id);
        setRun(r);
        if (r.status === "done" || r.status === "error") onFinished();
      } catch (e) {
        setError(String(e));
      }
    }, 800);
    return () => clearInterval(t);
  }, [run, onFinished]);

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setError("");
    setBusy(label);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="panel">
      <h2>Run the agent on a recipe</h2>
      {!live && <p className="muted">Showing the committed 25-recipe snapshot. Connect the Railway backend (Connection, top right) to run new recipes.</p>}
      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault();
          const r = (await act("run", () => api.startRun(url))) as Run | undefined;
          if (r) setRun(r);
        }}
      >
        <input className="grow" type="url" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://… recipe page with schema.org Recipe data" disabled={!canAdmin} />
        <button className="primary" disabled={!canAdmin || busy !== "" || (run !== null && (run.status === "queued" || run.status === "running"))}>
          Run
        </button>
      </form>
      {live && !settings.token() && <p className="muted">Add the admin token under Connection to run recipes.</p>}
      {run && (
        <div className="run">
          <div className="path">
            {run.node_path.length === 0 && <span className="muted">{run.status}…</span>}
            {run.node_path.map((n, i) => (
              <span key={i} className={`node ${n === "match_nutrition" ? "node-loop" : ""}`}>
                {n}
              </span>
            ))}
            {(run.status === "queued" || run.status === "running") && <span className="node node-pending">…</span>}
          </div>
          {run.terminal && (
            <p>
              <StatePill state={run.terminal.state} /> {run.terminal.reason}{" "}
              {run.recipe_id && <a href={`#/recipe/${run.recipe_id}`}>Open record →</a>}
            </p>
          )}
          {run.error && <p className="error">{run.error}</p>}
        </div>
      )}
      <div className="row actions">
        <a className={`button ${live ? "" : "disabled"}`} href={live ? api.pdfUrl() : undefined} target="_blank" rel="noreferrer">
          Download dataset PDF
        </a>
        <button disabled={!canAdmin || !config?.handoff_configured || busy !== ""} onClick={() => act("handoff", api.handoff)} title={config?.handoff_configured ? "" : "Set N8N_WEBHOOK_URL on the backend"}>
          {busy === "handoff" ? "Sending…" : "Send to n8n for approval"}
        </button>
        <button disabled={!canAdmin || busy !== ""} onClick={() => act("batch", api.startBatch)}>
          Re-run all 25
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  );
}

// ------------------------------------------------------------------------------------ dashboard
function Dashboard({ summary, rows, config, reload }: { summary: Summary | null; rows: Row[]; config: Config | null; reload: () => void }) {
  const [filter, setFilter] = useState<"all" | "complete" | "partial" | "card">("all");
  const shown = useMemo(
    () =>
      rows.filter((r) =>
        filter === "all" ? true : filter === "complete" ? r.nutrition_complete : filter === "partial" ? !r.nutrition_complete : r.card,
      ),
    [rows, filter],
  );
  return (
    <>
      {summary && (
        <section className="stats">
          <div className="stat">
            <b>{summary.recipes}</b>
            <span>recipes</span>
          </div>
          <div className="stat">
            <b>{pct(summary.match_rate)}</b>
            <span>
              ingredients matched ({summary.matched}/{summary.ingredients})
            </span>
          </div>
          <div className="stat">
            <b>{summary.ingredients_with_nutrition}</b>
            <span>with gram weight + nutrition</span>
          </div>
          <div className="stat">
            <b>{summary.unknown}</b>
            <span>unknown ({summary.hit_retry_cap} hit the cap)</span>
          </div>
          <div className="stat">
            <b>{summary.cards_produced}</b>
            <span>cook notes cards</span>
          </div>
        </section>
      )}
      <RunPanel config={config} onFinished={reload} />
      <section className="panel">
        <div className="row spread">
          <h2>Dataset</h2>
          <div className="seg">
            {(["all", "complete", "partial", "card"] as const).map((f) => (
              <button key={f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>
                {f === "card" ? "with card" : f}
              </button>
            ))}
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Recipe</th>
                <th>Terminal</th>
                <th className="num">Matched</th>
                <th>Nutrition</th>
                <th className="num">kcal (whole)</th>
                <th>Card</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.recipe_id} onClick={() => (window.location.hash = `#/recipe/${r.recipe_id}`)} className="clickable">
                  <td>
                    <a href={`#/recipe/${r.recipe_id}`}>{r.title}</a>
                    <div className="muted small">{r.site}</div>
                  </td>
                  <td>
                    <StatePill state={r.terminal.state} />
                  </td>
                  <td className="num">
                    {r.matched}/{r.ingredients}
                  </td>
                  <td>{r.nutrition_complete ? "complete" : `partial (${r.with_nutrition}/${r.ingredients})`}</td>
                  <td className="num">{n0(r.energy_kcal)}</td>
                  <td>{r.card ? "yes" : <span className="muted">{r.comment_count} comments</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

// ------------------------------------------------------------------------------------ detail
function RecipeDetail({ id }: { id: string }) {
  const [rec, setRec] = useState<RecipeRecord | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  useEffect(() => {
    setRec(null);
    api.recipe(id).then(setRec, (e) => setError(String(e)));
  }, [id]);
  if (error) return <p className="error">{error}</p>;
  if (!rec) return <p className="muted">Loading…</p>;
  const t = rec.nutrition.totals;
  return (
    <>
      <a href="#/">← All recipes</a>
      <section className="panel">
        <h1>{rec.title}</h1>
        <p className="muted small">
          {rec.recipe_id} · <a href={rec.source_url} target="_blank" rel="noreferrer">{rec.source_url}</a> · page from {rec.provenance.page_source} · yield {rec.yield_text ?? "not stated"}
        </p>
        <p>
          <StatePill state={rec.terminal.state} /> {rec.terminal.reason}
        </p>
        <div className="path">
          {rec.node_path.map((n, i) => (
            <span key={i} className={`node ${n.startsWith("match_nutrition") ? "node-loop" : ""} ${n.endsWith(":skipped") ? "node-skip" : ""}`}>
              {n}
            </span>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Nutrition</h2>
        <p className={rec.nutrition.complete ? "" : "warn"}>{rec.nutrition.statement}</p>
        <div className="kv">
          {[
            ["Energy", `${n0(t.energy_kcal)} kcal`],
            ["Protein", `${t.protein_g} g`],
            ["Fat", `${t.fat_g} g`],
            ["Carbohydrate", `${t.carbohydrate_g} g`],
            ["Sugars", `${t.sugars_g} g`],
            ["Sodium", `${n0(t.sodium_mg)} mg`],
          ].map(([k, v]) => (
            <div key={k}>
              <span className="muted small">{k}</span>
              <b>{v}</b>
            </div>
          ))}
          {rec.nutrition.per_serving && (
            <div>
              <span className="muted small">
                Per {(rec.servings_unit ?? "serving").replace(/s$/, "")} ({rec.servings})
              </span>
              <b>
                {n0(rec.nutrition.per_serving.energy_kcal)} kcal{!rec.nutrition.complete && <span className="muted small"> (partial)</span>}
              </b>
            </div>
          )}
        </div>
        <p className="muted small">{rec.provenance.nutrition_source}. Every number traces to the food id in its row.</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Ingredient (as written)</th>
                <th>USDA food</th>
                <th className="num">Grams</th>
                <th className="num">kcal</th>
                <th>Lookups</th>
              </tr>
            </thead>
            <tbody>
              {rec.ingredients.map((i) => (
                <Fragment key={i.index}>
                  <tr className="clickable" onClick={() => setOpen(open === i.index ? null : i.index)}>
                    <td>{i.raw}</td>
                    <td>
                      {i.food_id ? (
                        <>
                          <code>{i.food_id}</code> {i.food_description}
                        </>
                      ) : (
                        <span className="pill pill-unknown">unknown</span>
                      )}
                    </td>
                    <td className="num">{i.grams == null ? <span className="muted">–</span> : n0(i.grams)}</td>
                    <td className="num">{i.nutrients?.energy_kcal == null ? <span className="muted">–</span> : n0(i.nutrients.energy_kcal)}</td>
                    <td>
                      {i.attempts} {i.attempts === 1 ? "try" : "tries"} ▸
                    </td>
                  </tr>
                  {open === i.index && (
                    <tr className="detail-row">
                      <td colSpan={5}>
                        <ol className="attempts">
                          {i.attempt_log.map((a) => (
                            <li key={a.attempt}>
                              <code>{a.query}</code> <span className="muted">({a.strategy})</span> → <b>{a.outcome}</b>{" "}
                              {a.detail !== a.outcome && <span className="muted small">{a.detail}</span>}
                            </li>
                          ))}
                        </ol>
                        <div className="small">
                          {i.gram_basis && <>Grams: {i.gram_basis}. </>}
                          {i.unknown_reason && <>Unknown: {i.unknown_reason}</>}
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>Cook notes</h2>
        {rec.cook_notes.status === "produced" ? (
          <>
            <blockquote className="card">{rec.cook_notes.card}</blockquote>
            <p className="muted small">
              {rec.cook_notes.word_count} words (cap 60) · summariser {rec.cook_notes.backend}
            </p>
            <ul className="claims">
              {rec.cook_notes.claims.map((c) => (
                <li key={c.text}>
                  <b>
                    {c.count} of {rec.cook_notes.comment_count}
                  </b>{" "}
                  {c.text} <span className="muted small">comment ids {c.comment_ids.join(", ")}</span>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="muted">
            No card: {rec.cook_notes.comment_count} cook comments, below the threshold of {rec.cook_notes.threshold}.
          </p>
        )}
      </section>
    </>
  );
}

// ------------------------------------------------------------------------------------ app
export default function App() {
  const hash = useHashRoute();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  useEffect(() => {
    setError("");
    Promise.all([api.summary(), api.recipes(), api.config()])
      .then(([s, r, c]) => {
        setSummary(s);
        setRows(r);
        setConfig(c);
      })
      .catch((e) => setError(`Could not reach the backend (${e instanceof Error ? e.message : e}). Check the URL under Connection.`));
  }, [version]);

  const recipeId = hash.match(/^#\/recipe\/([\w-]+)/)?.[1];
  return (
    <div className="page">
      <header>
        <div>
          <a href="#/" className="brand">
            Recipe Research Agent
          </a>
          <div className="muted small">
            {summary?.category ?? "Dessert"} dataset · retry cap {summary?.retry_cap ?? 3} · comment threshold {summary?.comment_threshold ?? 5} · card cap {summary?.card_word_cap ?? 60} words
            {config && ` · summariser ${config.summariser}`}
          </div>
        </div>
        <div className="row">
          <span className={`mode ${api.live() ? "mode-live" : ""}`}>{api.live() ? "Live backend" : "Snapshot"}</span>
          <button onClick={() => setShowSettings((s) => !s)}>Connection</button>
        </div>
      </header>
      {showSettings && <SettingsPanel onClose={() => setShowSettings(false)} onSaved={reload} />}
      {error && <p className="error">{error}</p>}
      {recipeId ? <RecipeDetail id={recipeId} key={`${recipeId}-${version}`} /> : <Dashboard summary={summary} rows={rows} config={config} reload={reload} />}
      <footer className="muted small">
        Unmatched ingredients are recorded as unknown, never estimated. Nodes: {NODE_ORDER.join(" → ")}.
      </footer>
    </div>
  );
}
