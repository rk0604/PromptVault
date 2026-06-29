"""promptvault: store, run, and evaluate LLM prompts.

The entire public surface is three things, and that is by design — these are
the only three a user ever needs:

- ``experiment``: a context manager that registers a prompt experiment so its
  inputs and results are tracked and persisted.
- ``run``: execute a named prompt against the experiment's model and record
  the response plus its metrics.
- ``evaluate``: score a recorded run against developer-defined metrics.

Everything else in this package is an implementation detail and is not part
of the supported, importable API.
"""

import json
import threading
from datetime import datetime, timezone

from . import db
from . import runner
from . import evaluator

__all__ = ["experiment", "run", "evaluate"]

# Thread-local storage for the currently active experiment context.
_state = threading.local()


class experiment:
    """Context manager that registers and scopes a prompt experiment.

    Use with a ``with`` statement; ``run`` and ``evaluate`` only work inside
    the block::

        with experiment("my-test", "claude-opus-4-6", {"topic": "cats"}):
            result = run("summarize")
            evaluate(result, {"has_topic": lambda r: "cat" in r.lower()})
    """

    def __init__(self, name, model, vars=None):
        self.name = name
        self.model = model
        self.vars = vars or {}

    def __enter__(self):
        self.experiment_id = db.generate_id()
        vars_hash = runner.compute_vars_hash(self.vars)
        vars_snapshot = json.dumps(self.vars)
        db.insert_experiment(
            self.experiment_id, self.name, self.model, vars_snapshot, vars_hash
        )
        _state.experiment_id = self.experiment_id
        _state.model = self.model
        _state.vars = self.vars
        print(f"→ experiment '{self.name}' started ({self.experiment_id})")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _state.experiment_id = None
        _state.model = None
        _state.vars = None
        print(f"✓ experiment '{self.name}' complete")
        return False


def run(prompt_name):
    """Execute ``prompt_name`` against the active experiment's model.

    Must be called inside an ``experiment`` block. Returns a dict with
    everything ``evaluate`` needs: ``run_id``, ``response``, ``input_tokens``,
    ``output_tokens``, ``latency_ms``, ``cost_usd``, ``stop_reason``,
    ``model``, and ``prompt_hash``.
    """
    experiment_id = getattr(_state, "experiment_id", None)
    if not experiment_id:
        raise RuntimeError(
            "run() must be called inside a 'with experiment(...)' block."
        )

    model = _state.model
    vars = _state.vars

    system_template, user_template = runner.load_prompt(prompt_name)
    prompt_hash = runner.compute_hash(system_template, user_template)

    system_content = (
        runner.resolve_template(system_template, vars)
        if system_template is not None
        else None
    )
    user_content = runner.resolve_template(user_template, vars)

    captured = runner.call_llm(model, system_content, user_content)

    run_id = db.generate_id()
    timestamp = datetime.now(timezone.utc).isoformat()
    db.insert_run(
        run_id,
        experiment_id,
        prompt_name,
        prompt_hash,
        system_content,
        user_content,
        captured["response"],
        captured["input_tokens"],
        captured["output_tokens"],
        captured["latency_ms"],
        captured["cost_usd"],
        captured["stop_reason"],
        captured["model"],
        timestamp,
    )

    print(
        f"  run {run_id} | {captured['model']} | "
        f"{captured['input_tokens']}in {captured['output_tokens']}out | "
        f"{captured['latency_ms']}ms | ${captured['cost_usd']:.6f}"
    )

    return {
        "run_id": run_id,
        "response": captured["response"],
        "input_tokens": captured["input_tokens"],
        "output_tokens": captured["output_tokens"],
        "latency_ms": captured["latency_ms"],
        "cost_usd": captured["cost_usd"],
        "stop_reason": captured["stop_reason"],
        "model": captured["model"],
        "prompt_hash": prompt_hash,
    }


def evaluate(result, metrics):
    """Score a recorded ``run`` result against developer-defined ``metrics``.

    Must be called inside an ``experiment`` block. Returns the dict of raw
    metric values produced by the evaluators.
    """
    if not getattr(_state, "experiment_id", None):
        raise RuntimeError(
            "evaluate() must be called inside a 'with experiment(...)' block."
        )

    scores = evaluator.run_evaluators(result, metrics)
    for metric_name, value in scores.items():
        print(f"  score | {metric_name}: {value}")
    return scores
