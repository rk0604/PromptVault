"""Prompt execution for promptvault.

Loads prompt templates from the ``prompts/`` directory, resolves their
``{{var}}`` placeholders, and calls the appropriate LLM provider (Anthropic
or OpenAI) while capturing latency, token usage, and cost for each run.
"""

import hashlib
import json
import logging
import os
import re
import time

import anthropic
import openai

logger = logging.getLogger(__name__)

PROMPTS_DIR = "prompts"

# Approximate USD cost per token, keyed by model. (input, output) per token.
COST_PER_TOKEN = {
    "claude-haiku-4-5": {"input": 0.00000080, "output": 0.00000400},
    "claude-sonnet-4-6": {"input": 0.00000300, "output": 0.00001500},
    "claude-opus-4-6": {"input": 0.00001500, "output": 0.00007500},
    "gpt-4o": {"input": 0.00000250, "output": 0.00001000},
    "gpt-4o-mini": {"input": 0.00000015, "output": 0.00000060},
}

_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def load_prompt(prompt_name):
    """Load a prompt's user template (required) and system template (optional).

    Looks in the ``prompts/`` directory relative to the current working
    directory for ``{prompt_name}.txt`` and ``{prompt_name}.system.txt``.
    Returns ``(system_content_or_None, user_content)``.
    """
    user_path = os.path.join(PROMPTS_DIR, f"{prompt_name}.txt")
    system_path = os.path.join(PROMPTS_DIR, f"{prompt_name}.system.txt")

    if not os.path.exists(user_path):
        raise FileNotFoundError(
            f"User prompt template not found: '{user_path}'. "
            f"Expected a file named '{prompt_name}.txt' in the "
            f"'{PROMPTS_DIR}/' directory."
        )

    with open(user_path, "r", encoding="utf-8") as f:
        user_content = f.read()

    system_content = None
    if os.path.exists(system_path):
        with open(system_path, "r", encoding="utf-8") as f:
            system_content = f.read()

    return system_content, user_content


def resolve_template(template, vars):
    """Replace ``{{key}}`` placeholders in ``template`` with values from ``vars``.

    Raises ``KeyError`` with a clear message if a placeholder has no matching
    key in ``vars``.
    """
    def _replace(match):
        key = match.group(1)
        if key not in vars:
            raise KeyError(
                f"Template placeholder '{{{{{key}}}}}' has no matching key in vars. "
                f"Available keys: {sorted(vars.keys())}."
            )
        return str(vars[key])

    return _PLACEHOLDER_RE.sub(_replace, template)


def compute_hash(system_content, user_content):
    """Return the first 8 hex chars of sha256(system + "\\n" + user).

    Operates on the raw template strings (before vars are filled in). A
    ``None`` system template is treated as an empty string.
    """
    combined = (system_content or "") + "\n" + user_content
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:8]


def compute_vars_hash(vars):
    """Return the first 8 hex chars of sha256 over the JSON-serialized vars.

    Keys are sorted before serialization so the hash is deterministic.
    """
    serialized = json.dumps(vars, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:8]


def call_llm(model, system_content, user_content):
    """Call the LLM provider for ``model`` and capture run metrics.

    Dispatches to the Anthropic SDK for ``claude*`` models and the OpenAI SDK
    for ``gpt*`` models. Returns a dict with ``response``, ``input_tokens``,
    ``output_tokens``, ``latency_ms``, ``cost_usd``, ``stop_reason``, and
    ``model``.
    """
    start = time.time()

    if model.startswith("claude"):
        response, input_tokens, output_tokens, stop_reason = _call_anthropic(
            model, system_content, user_content
        )
    elif model.startswith("gpt"):
        response, input_tokens, output_tokens, stop_reason = _call_openai(
            model, system_content, user_content
        )
    else:
        raise ValueError(
            f"Unsupported model '{model}': expected a name starting with "
            f"'claude' or 'gpt'."
        )

    latency_ms = int((time.time() - start) * 1000)
    cost_usd = _compute_cost(model, input_tokens, output_tokens)

    return {
        "response": response,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "cost_usd": cost_usd,
        "stop_reason": stop_reason,
        "model": model,
    }


def _call_anthropic(model, system_content, user_content):
    """Call the Anthropic Messages API and extract response fields."""
    client = anthropic.Anthropic()

    kwargs = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": user_content}],
    }
    if system_content is not None:
        kwargs["system"] = system_content

    message = client.messages.create(**kwargs)

    response = "".join(
        block.text for block in message.content if block.type == "text"
    )
    input_tokens = message.usage.input_tokens
    output_tokens = message.usage.output_tokens
    stop_reason = message.stop_reason

    return response, input_tokens, output_tokens, stop_reason


def _call_openai(model, system_content, user_content):
    """Call the OpenAI Chat Completions API and extract response fields."""
    client = openai.OpenAI()

    messages = []
    if system_content is not None:
        messages.append({"role": "system", "content": system_content})
    messages.append({"role": "user", "content": user_content})

    completion = client.chat.completions.create(model=model, messages=messages)

    response = completion.choices[0].message.content
    input_tokens = completion.usage.prompt_tokens
    output_tokens = completion.usage.completion_tokens
    stop_reason = completion.choices[0].finish_reason

    return response, input_tokens, output_tokens, stop_reason


def _compute_cost(model, input_tokens, output_tokens):
    """Compute USD cost from token counts using COST_PER_TOKEN."""
    rates = COST_PER_TOKEN.get(model)
    if rates is None:
        logger.warning(
            "No cost data for model '%s'; recording cost_usd as 0.0.", model
        )
        return 0.0
    return input_tokens * rates["input"] + output_tokens * rates["output"]
