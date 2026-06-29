"""Persistence layer for promptvault.

Manages all SQLite interactions against a ``promptvault.db`` file in the
current working directory: connection setup, schema creation, and row inserts
for experiments, runs, and scores. Uses the Python standard library only.
"""

import os
import secrets
import sqlite3
from datetime import datetime, timezone

DB_FILENAME = "promptvault.db"


def get_connection():
    """Open a connection to ``promptvault.db`` in the current working directory.

    Configures the connection so that rows are accessible by column name,
    WAL journaling is enabled for safer concurrent access, and the connection
    may be shared across threads.
    """
    conn = sqlite3.connect(DB_FILENAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def initialize():
    """Create the experiments, runs, and scores tables if they don't exist."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                experiment_id   TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                model           TEXT NOT NULL,
                vars_snapshot   TEXT NOT NULL,
                vars_hash       TEXT NOT NULL,
                created_at      TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id           TEXT PRIMARY KEY,
                experiment_id    TEXT NOT NULL REFERENCES experiments(experiment_id),
                prompt_name      TEXT NOT NULL,
                prompt_hash      TEXT NOT NULL,
                system_snapshot  TEXT,
                user_snapshot    TEXT NOT NULL,
                response         TEXT NOT NULL,
                input_tokens     INTEGER NOT NULL,
                output_tokens    INTEGER NOT NULL,
                latency_ms       INTEGER NOT NULL,
                cost_usd         REAL NOT NULL,
                stop_reason      TEXT,
                model            TEXT NOT NULL,
                timestamp        TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scores (
                score_id     TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL REFERENCES runs(run_id),
                metric_name  TEXT NOT NULL,
                value        TEXT NOT NULL,
                value_type   TEXT NOT NULL,
                created_at   TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def insert_experiment(experiment_id, name, model, vars_snapshot, vars_hash):
    """Insert one row into the experiments table.

    The ``created_at`` timestamp is generated here as an ISO 8601 string.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO experiments (
                experiment_id, name, model, vars_snapshot, vars_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (experiment_id, name, model, vars_snapshot, vars_hash, _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def insert_run(
    run_id,
    experiment_id,
    prompt_name,
    prompt_hash,
    system_snapshot,
    user_snapshot,
    response,
    input_tokens,
    output_tokens,
    latency_ms,
    cost_usd,
    stop_reason,
    model,
    timestamp,
):
    """Insert one row into the runs table."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO runs (
                run_id, experiment_id, prompt_name, prompt_hash,
                system_snapshot, user_snapshot, response,
                input_tokens, output_tokens, latency_ms, cost_usd,
                stop_reason, model, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                experiment_id,
                prompt_name,
                prompt_hash,
                system_snapshot,
                user_snapshot,
                response,
                input_tokens,
                output_tokens,
                latency_ms,
                cost_usd,
                stop_reason,
                model,
                timestamp,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_score(score_id, run_id, metric_name, value, value_type):
    """Insert one row into the scores table.

    The ``created_at`` timestamp is generated here as an ISO 8601 string.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO scores (
                score_id, run_id, metric_name, value, value_type, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (score_id, run_id, metric_name, value, value_type, _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def generate_id():
    """Return a random 8 character hex string for use as a primary key."""
    return secrets.token_hex(4)


def _now_iso():
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# Ensure the schema exists as soon as the module is imported.
initialize()
