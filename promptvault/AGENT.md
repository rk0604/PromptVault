# PromptVault — Agent Guide (root)

PromptVault is a minimal local SDK for running LLM prompts and storing their results, metrics, and scores in SQLite.

## Public API

Three functions. Nothing else is public.

- `experiment(name, model, vars)` — context manager that registers and scopes an experiment.
- `run(prompt_name)` — loads a prompt, calls the model, records the run. Returns a result dict.
- `evaluate(result, metrics)` — scores a run with developer-defined metric callables.

## Data model

Two-tier hierarchy, parent to child:

```
experiment ──< run ──< score
```

- One experiment contains many runs.
- One run contains many scores.
- A run cannot exist without an experiment. A score cannot exist without a run.

## Auto-captured vs developer-defined

Auto-captured per run: `response`, `input_tokens`, `output_tokens`, `latency_ms`, `cost_usd`, `stop_reason`, `model`, `prompt_hash`, `vars_hash`, timestamps.

Developer-defined: the prompt templates, the `vars` dict, the model string, and the metric lambdas passed to `evaluate`.

## Internal modules

- `promptvault/__init__.py` — the public API (`experiment`, `run`, `evaluate`) and thread-local state.
- `promptvault/runner.py` — loads prompts, resolves templates, calls the LLM, captures metrics, computes hashes.
- `promptvault/evaluator.py` — runs metric callables and infers score value types.
- `promptvault/db.py` — all SQLite access: connection, schema, inserts, id generation.

## Never do this

- Never add built-in metrics or opinions about response quality.
- Never add cloud sync, auth, or team features.
- Never let runs exist outside an experiment context.
- Never add external dependencies beyond `anthropic` and `openai`.
- Never expose internal functions in `__init__.py`.
