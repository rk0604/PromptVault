# PromptVault — Agent Guide (src)

## Files

- `__init__.py` — defines the public API and holds thread-local experiment state.
- `runner.py` — loads prompt files, resolves `{{var}}` placeholders, calls the LLM, computes hashes and cost.
- `evaluator.py` — executes metric callables and infers each score's value type.
- `db.py` — owns every SQLite operation: connection, schema, inserts, id generation.

## Public API surface

Exactly three names are exported from `__init__.py`: `experiment`, `run`, `evaluate`. Nothing else.

## SQLite schema

Database file: `promptvault.db` in the current working directory. WAL mode enabled.

**experiments**
- `experiment_id` TEXT PRIMARY KEY
- `name` TEXT NOT NULL
- `model` TEXT NOT NULL
- `vars_snapshot` TEXT NOT NULL — JSON string of vars
- `vars_hash` TEXT NOT NULL — sha256 of vars_snapshot
- `created_at` TEXT NOT NULL — ISO 8601

**runs**
- `run_id` TEXT PRIMARY KEY
- `experiment_id` TEXT NOT NULL REFERENCES experiments(experiment_id)
- `prompt_name` TEXT NOT NULL
- `prompt_hash` TEXT NOT NULL
- `system_snapshot` TEXT — resolved system prompt sent to API (nullable)
- `user_snapshot` TEXT NOT NULL — resolved user prompt sent to API
- `response` TEXT NOT NULL
- `input_tokens` INTEGER NOT NULL
- `output_tokens` INTEGER NOT NULL
- `latency_ms` INTEGER NOT NULL
- `cost_usd` REAL NOT NULL
- `stop_reason` TEXT
- `model` TEXT NOT NULL
- `timestamp` TEXT NOT NULL — ISO 8601

**scores**
- `score_id` TEXT PRIMARY KEY
- `run_id` TEXT NOT NULL REFERENCES runs(run_id)
- `metric_name` TEXT NOT NULL
- `value` TEXT NOT NULL — always stored as string
- `value_type` TEXT NOT NULL — one of: bool, int, float, str
- `created_at` TEXT NOT NULL — ISO 8601

## State flow through a run

1. `experiment.__enter__` writes `experiment_id`, `model`, `vars` to `_state` (a `threading.local`).
2. `run` reads `_state`; raises `RuntimeError` if no active experiment. It returns a result dict containing `run_id` plus all captured fields.
3. `evaluate` reads that result dict (uses `result["response"]` and `result["run_id"]`); raises `RuntimeError` if no active experiment.
4. `experiment.__exit__` clears `_state`.

## Hashing

- `prompt_hash` = first 8 chars of `sha256( (system or "") + "\n" + user )`, on RAW templates BEFORE vars are filled in.
- `vars_hash` = first 8 chars of `sha256( json.dumps(vars, sort_keys=True) )`. Sorted keys make it deterministic.

## Score value type inference

`infer_value_type(value)` returns `(stringified, type)`. Check order matters:
`None` → `("none","str")`; `bool` (before int) → lowercased; `int`; `float`; `str`; anything else → `str(value)` with type `str`.

## API keys

Read from environment by each SDK: `anthropic.Anthropic()` uses `ANTHROPIC_API_KEY`, `openai.OpenAI()` uses `OPENAI_API_KEY`. Never hardcode keys.
