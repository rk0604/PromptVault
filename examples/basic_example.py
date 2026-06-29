# PromptVault basic example
# Run this file directly: python examples/basic_example.py
# Expected output: experiment start, run metrics, scores, response text
# This example requires ANTHROPIC_API_KEY in your environment
"""Minimal end-to-end PromptVault example: define vars, run a prompt, score it.

The whole SDK in one screen — ``experiment`` scopes a run, ``run`` calls the
model, and ``evaluate`` scores the response.
"""

from promptvault import experiment, run, evaluate

text = (
    "The James Webb Space Telescope launched in December 2021. "
    "It observes the universe primarily in infrared light. "
    "This lets it see the earliest galaxies formed after the Big Bang. "
    "It orbits the Sun about 1.5 million kilometers from Earth."
)

with experiment(name="summarizer-test", model="claude-sonnet-4-6", vars={"text": text}):
    result = run("summarize")
    evaluate(result, {
        "under_100_words": lambda r: len(r.split()) < 100,
        "ends_with_period": lambda r: r.strip().endswith("."),
        "no_bullet_points": lambda r: "•" not in r and "-" not in r,
    })
    print(result["response"])
