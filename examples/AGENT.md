# PromptVault — Agent Guide (examples)

## Run the basic example

Run from the project root (where `prompts/` lives). Requires `ANTHROPIC_API_KEY` in the environment.

```bash
python examples/basic_example.py
```

`load_prompt` resolves `prompts/` relative to the current working directory. Running from elsewhere raises `FileNotFoundError`.

## Expected terminal output

```
→ experiment 'summarizer-test' started ({experiment_id})
  run {run_id} | claude-sonnet-4-6 | {n}in {n}out | {n}ms | $0.000xxx
  score | under_100_words: True
  score | ends_with_period: True
  score | no_bullet_points: True
{the model's response text}
✓ experiment 'summarizer-test' complete
```

Ids and numbers vary per run. On a non-UTF-8 Windows console, set `PYTHONUTF8=1` so `→`/`✓` print.

## Add a new prompt

Create `prompts/{name}.txt` (user template, required). Optionally create `prompts/{name}.system.txt` (system template). Use `{{var}}` placeholders; every placeholder must have a matching key in `vars`. Then call `run("{name}")`.

## Add a new metric

Add a `name: lambda r: ...` entry to the dict passed to `evaluate`. `r` is the response text. Return `bool`, `int`, `float`, `str`, or `None`. `None` stores a manual placeholder. A raising lambda stores `"error"`.

```python
evaluate(result, {
    "under_100_words": lambda r: len(r.split()) < 100,
    "mentions_topic": lambda r: "webb" in r.lower(),
})
```

## Run a model comparison

Use two experiments, same prompt and vars, different model strings.

```python
for model in ("claude-sonnet-4-6", "gpt-4o"):
    with experiment("compare", model, vars={"text": text}):
        result = run("summarize")
        evaluate(result, {"under_100_words": lambda r: len(r.split()) < 100})
```

Equal `vars_hash` and `prompt_hash` across rows confirm identical inputs.

## Query results from SQLite

The database is `promptvault.db` in the directory you ran from.

```bash
sqlite3 promptvault.db "SELECT model, input_tokens, output_tokens, cost_usd FROM runs;"
sqlite3 promptvault.db "SELECT metric_name, value, value_type FROM scores;"
sqlite3 promptvault.db "SELECT r.model, s.metric_name, s.value FROM runs r JOIN scores s ON s.run_id = r.run_id;"
```
