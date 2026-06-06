from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


DB_PATH = Path("nira.db")


def _json_dumps(data: dict[str, Any] | None) -> str:
    return json.dumps(data or {}, ensure_ascii=False, default=str)


class OperationsStore:
    """
    Persistent operations database for NIRA.

    Stores real business records separately from session state:
    - tickets
    - payment commitments
    - voice interactions
    """

    def __init__(self, db_path: str | Path = DB_PATH) -> None:
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT NOT NULL UNIQUE,
                    session_id TEXT NOT NULL,
                    customer_name TEXT,
                    phone TEXT,
                    category TEXT NOT NULL,
                    priority TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    summary TEXT NOT NULL,
                    assigned_team TEXT,
                    source_agent TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_commitments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    customer_name TEXT,
                    phone TEXT,
                    commitment_amount REAL,
                    commitment_time TEXT,
                    payment_status TEXT,
                    source_agent TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    intent TEXT,
                    agent TEXT,
                    audio_path TEXT,
                    channel TEXT NOT NULL DEFAULT 'realtime_voice',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_operation_tickets_session ON operation_tickets(session_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_payment_commitments_session ON payment_commitments(session_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_voice_interactions_session ON voice_interactions(session_id);"
            )

            conn.commit()

    def create_ticket(
        self,
        *,
        ticket_id: str,
        session_id: str,
        category: str,
        summary: str,
        customer_name: str | None = None,
        phone: str | None = None,
        priority: str | None = None,
        status: str = "open",
        assigned_team: str | None = None,
        source_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO operation_tickets (
                    ticket_id,
                    session_id,
                    customer_name,
                    phone,
                    category,
                    priority,
                    status,
                    summary,
                    assigned_team,
                    source_agent,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ticket_id,
                    session_id,
                    customer_name,
                    phone,
                    category,
                    priority,
                    status,
                    summary,
                    assigned_team,
                    source_agent,
                    _json_dumps(metadata),
                    now,
                    now,
                ),
            )
            conn.commit()

    def create_payment_commitment(
        self,
        *,
        session_id: str,
        customer_name: str | None = None,
        phone: str | None = None,
        commitment_amount: float | None = None,
        commitment_time: str | None = None,
        payment_status: str | None = None,
        source_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO payment_commitments (
                    session_id,
                    customer_name,
                    phone,
                    commitment_amount,
                    commitment_time,
                    payment_status,
                    source_agent,
                    metadata_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    session_id,
                    customer_name,
                    phone,
                    commitment_amount,
                    commitment_time,
                    payment_status,
                    source_agent,
                    _json_dumps(metadata),
                    now,
                    now,
                ),
            )
            conn.commit()

    def create_voice_interaction(
        self,
        *,
        session_id: str,
        transcript: str,
        response_text: str,
        intent: str | None = None,
        agent: str | None = None,
        audio_path: str | None = None,
        channel: str = "realtime_voice",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO voice_interactions (
                    session_id,
                    transcript,
                    response_text,
                    intent,
                    agent,
                    audio_path,
                    channel,
                    metadata_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    session_id,
                    transcript,
                    response_text,
                    intent,
                    agent,
                    audio_path,
                    channel,
                    _json_dumps(metadata),
                    now,
                ),
            )
            conn.commit()


operations_store = OperationsStore()