"""Mocked end-to-end test of the experiment -> run -> evaluate flow.

No real API key or network call is made. The Anthropic client is patched and
its response is built to mirror a real Anthropic message: a content block with
``type == "text"`` (the field promptvault filters on) plus a usage object.
Running each test inside a temporary working directory keeps ``promptvault.db``
and the ``prompts/`` fixtures isolated from the repo.
"""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from promptvault import experiment, run, evaluate


def make_anthropic_response(text, input_tokens=50, output_tokens=10,
                            stop_reason="end_turn"):
    """Build a MagicMock shaped like a real Anthropic Messages response.

    The crucial detail (and the bug in the original ad-hoc mock) is that the
    content block sets ``type = "text"``. promptvault extracts response text
    with ``... if block.type == "text"``; without it, the text is dropped and
    the response collapses to an empty string.
    """
    block = MagicMock()
    block.type = "text"
    block.text = text

    response = MagicMock()
    response.content = [block]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    response.stop_reason = stop_reason
    return response


class MockFlowTest(unittest.TestCase):
    def setUp(self):
        # Isolate cwd so the test owns its prompts/ and promptvault.db.
        self._origin = os.getcwd()
        self._tmp = tempfile.mkdtemp()
        os.chdir(self._tmp)
        # No explicit initialize() needed: get_connection() ensures the schema
        # in whatever promptvault.db the current directory resolves to, so this
        # fresh temp workspace gets its tables created on first use.
        os.makedirs("prompts")
        with open("prompts/summarize.txt", "w", encoding="utf-8") as f:
            f.write("Summarize the following text: {{text}}")
        with open("prompts/summarize.system.txt", "w", encoding="utf-8") as f:
            f.write("You are a concise summarizer.")

    def tearDown(self):
        os.chdir(self._origin)

    def test_response_text_flows_through(self):
        mock_response = make_anthropic_response("This is a mocked summary.")

        with patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response

            with experiment("test-run", model="claude-sonnet-4-6",
                            vars={"text": "hello"}):
                result = run("summarize")
                scores = evaluate(result, {
                    "under_100_words": lambda r: len(r.split()) < 100,
                    "ends_with_period": lambda r: r.strip().endswith("."),
                    "always_none": None,
                    "always_fails": lambda r: 1 / 0,
                })

        # The mocked text actually reaches the result (the original bug).
        self.assertEqual(result["response"], "This is a mocked summary.")
        self.assertEqual(result["input_tokens"], 50)
        self.assertEqual(result["output_tokens"], 10)
        self.assertEqual(result["stop_reason"], "end_turn")
        self.assertEqual(result["model"], "claude-sonnet-4-6")
        self.assertIn("run_id", result)
        self.assertIn("prompt_hash", result)

        # Metrics now score the real summary, not an empty string.
        self.assertEqual(scores["under_100_words"], True)
        self.assertEqual(scores["ends_with_period"], True)   # was False on ''
        self.assertIsNone(scores["always_none"])             # manual placeholder
        self.assertIsNone(scores["always_fails"])            # raised -> caught

    def test_api_was_called_once_with_resolved_prompt(self):
        mock_response = make_anthropic_response("ok.")

        with patch("anthropic.Anthropic") as mock_client:
            create = mock_client.return_value.messages.create
            create.return_value = mock_response

            with experiment("call-shape", model="claude-sonnet-4-6",
                            vars={"text": "penguins"}):
                run("summarize")

            create.assert_called_once()
            kwargs = create.call_args.kwargs
            self.assertEqual(kwargs["model"], "claude-sonnet-4-6")
            self.assertEqual(kwargs["system"], "You are a concise summarizer.")
            self.assertEqual(
                kwargs["messages"][0]["content"],
                "Summarize the following text: penguins",  # {{text}} resolved
            )

    def test_rows_persisted_to_sqlite(self):
        mock_response = make_anthropic_response("Persisted summary.")

        with patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response

            with experiment("persist", model="claude-sonnet-4-6",
                            vars={"text": "hello"}):
                result = run("summarize")
                evaluate(result, {"ok": lambda r: True})

        conn = sqlite3.connect("promptvault.db")
        self.assertEqual(conn.execute("SELECT count(*) FROM experiments").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT count(*) FROM runs").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT count(*) FROM scores").fetchone()[0], 1)
        response = conn.execute("SELECT response FROM runs").fetchone()[0]
        self.assertEqual(response, "Persisted summary.")
        conn.close()

    def test_schema_created_after_chdir(self):
        """Regression: the schema must exist even when cwd changes after import.

        This is the scenario that originally raised 'no such table: experiments'
        because initialize() ran only once at import-time cwd.
        """
        mock_response = make_anthropic_response("Fresh dir summary.")
        deeper = os.path.join(self._tmp, "nested", "workdir")
        os.makedirs(os.path.join(deeper, "prompts"))
        with open(os.path.join(deeper, "prompts", "summarize.txt"),
                  "w", encoding="utf-8") as f:
            f.write("Summarize: {{text}}")
        os.chdir(deeper)  # change cwd well after promptvault was imported

        with patch("anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = mock_response
            with experiment("after-chdir", model="claude-sonnet-4-6",
                            vars={"text": "hi"}):
                result = run("summarize")

        self.assertEqual(result["response"], "Fresh dir summary.")
        self.assertTrue(os.path.exists("promptvault.db"))


if __name__ == "__main__":
    unittest.main()
