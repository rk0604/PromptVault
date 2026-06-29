# PromptVault

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

PromptVault is a lightweight Python SDK for tracking LLM prompt evaluations locally. You define the metrics. PromptVault tracks how they evolve.

## Install

```bash
pip install promptvault
```

## Quickstart

```python
from promptvault import experiment, run, evaluate

with experiment(name="summarizer-test", model="claude-sonnet-4-6", vars={"text": text}):
    result = run("summarize")
    evaluate(result, {"under_100_words": lambda r: len(r.split()) < 100})
    print(result["response"])
```

```
→ experiment 'summarizer-test' started (fc5dbdd6)
  run ba5089cd | claude-sonnet-4-6 | 60in 38out | 720ms | $0.000750
  score | under_100_words: True
✓ experiment 'summarizer-test' complete
```

## How it works

An **experiment** locks in a model and a `vars` dict. Every run inside it uses the same inputs, so comparisons across prompt versions and models are actually meaningful.

A **run** loads a prompt, calls the API, and auto-captures everything it returns: response, token counts, latency, cost, and stop reason. You write nothing to log these.

**`evaluate()`** runs your metric functions against the response and stores each result in a local SQLite file (`promptvault.db`). The metrics are yours — booleans, numbers, strings, whatever you decide "better" means.

## Prompt files

Prompts live as plain text files in `prompts/`:

```
prompts/
  summarize.txt          # user template (required)
  summarize.system.txt   # system template (optional)
```

Templates use `{{var}}` placeholders, filled from the experiment's `vars`:

```
Summarize the following text in 2-3 sentences: {{text}}
```

Git tracks your prompt history; PromptVault tracks which runs used which version (via `prompt_hash`).

## Querying your results

`promptvault.db` is plain SQLite. Query it however you like.

How a metric evolved across prompt versions:

```sql
SELECT r.prompt_hash, s.value
FROM runs r JOIN scores s ON s.run_id = r.run_id
WHERE r.prompt_name = 'summarize' AND s.metric_name = 'under_100_words'
ORDER BY r.timestamp;
```

How the same prompt performs across models:

```sql
SELECT r.model, s.metric_name, s.value
FROM runs r JOIN scores s ON s.run_id = r.run_id
WHERE r.prompt_name = 'summarize'
ORDER BY r.model;
```

## Why not X

- **DeepEval / RAGAS** — opinionated built-in metrics, not yours.
- **LangSmith / Braintrust** — cloud services with accounts; not local.
- **Rolling your own logger** — no structure, and a combinatorial mess once you try to compare versions × models × metrics.

## Roadmap

- **v1.1** — LLM-as-judge built-in evaluator.
- **v1.2** — pytest plugin so evals run in CI.
- **v1.3** — CLI command to print an evolution table in the terminal.
