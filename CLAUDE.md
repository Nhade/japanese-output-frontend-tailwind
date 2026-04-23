# CLAUDE.md

Project notes for Claude Code sessions working on this repo. Keep it short;
treat it as the shared map across web and local sessions.

## Repo layout

- `apps/backend/` — Flask + LangGraph. SQLite at `data/news_corpus.db`.
  Service modules expose `create_*_tables(conn)`; `app.py` calls them on
  startup.
  - `graphs/` — LangGraph workflows (chat, eval, review, video, and planned
    `practice_graph.py`).
  - `tools/` — typed tools used by agent graphs (conjugate, detect_pattern,
    lookup).
- `apps/frontend/` — Vue 3 + Vite + Pinia + Tailwind + Reka UI.
- `tools/` (repo root) — offline CLI utilities (backfill, fetchers); **not**
  the same as the agent tools under `apps/backend/tools/`.
- `tests/unit`, `tests/integration` — pytest; `conftest.py` at repo root adds
  `apps/backend` to `sys.path`.

## Active feature: grammar pattern practice

Branch: `feature/grammar-pattern-practice`.

Goal: let learners upload grammar notes / textbook sections, pick a range, and
practice the patterns in that range with varied exercise types.

### Design principle

**Agents plan and phrase; code retrieves and checks.** Every LLM factual
mistake (bad 活用, wrong JLPT, nonexistent pattern) migrates from agent to
tool. Every stilted template migrates from code to agent. The balance is set
per-node, not globally.

### Architecture

1. **Two-tier ingestion** on document upload:
   - Tier 1: raw `doc_chunks` (structural split on headings). For future
     semantic grounding.
   - Tier 2: structured extraction into `grammar_patterns` + `pattern_examples`
     via an LLM pass with Pydantic-constrained output and per-entry
     confidence. Above threshold auto-publishes; below is excluded from the
     planner.

2. **Three-node practice graph** (`graphs/practice_graph.py`):
   - `plan` — structured output `PracticePlan{target_pattern_id, strategy,
     difficulty, variant_hint}`. Temp 0. Cannot invent IDs.
   - `execute` — strategy-dispatched. Closed types (cloze, conjugation,
     translation) are template + table. Open types call LLM with tight prompt.
   - `verify` — deterministic checks (detect_pattern, expected-fits-blank,
     JLPT±1). Bounded retry on fail. Fallback to canonical example.

3. **Evaluation** (`graphs/eval_graph.py`, type-aware branch):
   - Closed → exact match.
   - Open → rubric LLM judge **that calls tools** (`detect_pattern`,
     `conjugate`), not judges from memory. Temp 0.

4. **Tools over free generation**:
   - `conjugate(verb, form)` — janome + rule engine. LLM never conjugates.
   - `detect_pattern(sentence, pattern_id)` — morphological check.
   - `lookup_pattern`, `search_examples`, `srs_due`, `learner_weak_points`.

5. **Temperature per node**: planner/evaluator temp 0; surface generator
   moderate; extraction temp 0.

6. **Exercise cache** keyed on `(pattern_id, strategy, seed)` — review
   sessions replay from cache; new sessions re-roll.

### v1 scope (this branch)

- One doc type: grammar notes in Markdown/TXT.
- One strategy: `pattern_use`.
- Two tools: `conjugate`, `detect_pattern`.
- Full loop: upload → extract → range-select → planner → executor → verifier
  → evaluator → feedback.

### Explicitly deferred

- PDF ingest.
- Semantic retrieval / free-chat grounding (schema ready, embeddings not
  populated).
- Cloze / conjugation / translation / free-chat strategies.
- Real SRS scheduling (stubbed uniform).
- Human review UI for low-confidence extractions.

### v1 defaults

- Extraction trigger: synchronous on upload.
- Confidence threshold: 0.8 auto-publish.
- Prompt locale: matches learner's locale (English / Traditional Chinese).
- Extraction model: same LLM as chat.

## Conventions

- Table creation: per-service `create_*_tables(conn: sqlite3.Connection)`,
  wired into `app.py` startup.
- IDs: TEXT UUIDs (matches existing `users`, `videos`, `exercise` tables).
- New exercise types go in a single `exercises` table with a `type` column
  and polymorphic `expected_json` / `rubric_json`.
- Agent tools live in `apps/backend/tools/`. Each tool is a pure function
  with typed inputs/outputs — no implicit DB access beyond a passed
  connection.
- LangGraph state is a TypedDict; avoid globals.
