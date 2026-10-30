"""Approval queue (SQLite): AI drafts wait here until a human approves, edits or rejects them."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  lead_json TEXT NOT NULL,
  qualification_json TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | sent
  decided_at TEXT
);
"""


class ApprovalQueue:
    def __init__(self, path: str = "data/leads.db"):
        if path != ":memory:":
            from pathlib import Path

            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def add(self, lead: dict, qualification: dict, draft: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO drafts (created_at, lead_json, qualification_json, subject, body) VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), json.dumps(lead), json.dumps(qualification), draft["subject"], draft["body"]),
        )
        self.db.commit()
        return cur.lastrowid

    def get(self, draft_id: int) -> dict | None:
        row = self.db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return _row(row) if row else None

    def list(self, status: str | None = "pending") -> list[dict]:
        sql, args = "SELECT * FROM drafts", ()
        if status:
            sql, args = sql + " WHERE status=?", (status,)
        rows = self.db.execute(sql + " ORDER BY json_extract(qualification_json,'$.score') DESC, id", args).fetchall()
        return [_row(r) for r in rows]

    def decide(self, draft_id: int, status: str, subject: str | None = None, body: str | None = None) -> dict:
        if status not in {"approved", "rejected", "sent"}:
            raise ValueError("status must be approved, rejected or sent")
        current = self.get(draft_id)
        if not current:
            raise KeyError(draft_id)
        if current["status"] != "pending" and status != "sent":
            raise ValueError(f"Draft already {current['status']}")
        self.db.execute(
            "UPDATE drafts SET status=?, subject=?, body=?, decided_at=? WHERE id=?",
            (status, subject or current["subject"], body or current["body"], datetime.now(timezone.utc).isoformat(), draft_id),
        )
        self.db.commit()
        return self.get(draft_id)


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["lead"] = json.loads(d.pop("lead_json"))
    d["qualification"] = json.loads(d.pop("qualification_json"))
    return d
