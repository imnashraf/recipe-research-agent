# Check 3: interrupt, resume from checkpoint, compare with an uninterrupted run

Recipe: https://www.zenbelly.com/gingerbread/ (3 lookup rounds, give-up, summarise: the longest path).

## 1. Process killed with SIGKILL

- Started the batch CLI for this recipe; killed the process group as soon as the run log showed the first `match_round` event. Nodes completed before the kill: `fetch → parse_recipe → parse_ingredients → match_nutrition`.
- No record had been written at kill time. Same command run again: it logged `resume` from `['match_nutrition']` and did NOT re-run fetch.
- Nodes run after resume: `match_nutrition → match_nutrition → mark_unknown → gather_comments → summarise → validate → write`.
- Record after resume equals the uninterrupted record: **True** (full JSON equality, 14877 bytes).
- Node path recorded in the resumed record: `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → match_nutrition → mark_unknown → gather_comments → summarise → validate → write`.

## 2. Crash injected inside the retry loop (2nd match_nutrition call)

- Checkpointed node path at the crash: `fetch → parse_recipe → parse_ingredients → match_nutrition`; next node to run: `['match_nutrition']`.
- Resumed with `graph.ainvoke(None, config)`: 22 MCP calls after resume (only the remaining lookup rounds).
- Record after resume equals the uninterrupted record: **True**.

The run is resumable because each node returns a state update that the SQLite checkpointer saves (`durability="sync"`) before the next node starts; the thread id is derived from the URL and run label, so re-running the same command finds the unfinished thread.
