"""Evaluation for promptvault.

Runs developer-defined metric callables over a recorded LLM response and
stores each resulting score in SQLite via the ``db`` module.
"""

from . import db


def infer_value_type(value):
    """Return ``(stringified_value, type_string)`` for a raw metric value.

    ``type_string`` is one of ``bool``, ``int``, ``float``, or ``str``. ``bool``
    is checked before ``int`` since ``bool`` subclasses ``int``. ``None`` maps to
    ``("none", "str")``, representing a metric to be filled in manually later.
    """
    if value is None:
        return ("none", "str")
    if isinstance(value, bool):
        return (str(value).lower(), "bool")
    if isinstance(value, int):
        return (str(value), "int")
    if isinstance(value, float):
        return (str(value), "float")
    if isinstance(value, str):
        return (value, "str")
    return (str(value), "str")


def run_evaluators(result, metrics):
    """Score ``result`` with each metric in ``metrics`` and persist the scores.

    ``metrics`` maps metric names to callables (called with the response text)
    or ``None`` (stored as a manual placeholder). Returns ``{metric_name: value}``.
    """
    raw_values = {}
    for name, metric in metrics.items():
        if metric is None:
            value = None
        elif callable(metric):
            try:
                value = metric(result["response"])
            except Exception as exc:
                print(f"Warning: metric '{name}' raised an error: {exc}")
                db.insert_score(db.generate_id(), result["run_id"], name, "error", "str")
                raw_values[name] = None
                continue
        else:
            value = metric
        stringified, value_type = infer_value_type(value)
        db.insert_score(db.generate_id(), result["run_id"], name, stringified, value_type)
        raw_values[name] = value
    return raw_values
