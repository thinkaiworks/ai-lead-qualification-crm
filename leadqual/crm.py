"""Save qualified leads to the CRM. HubSpot built in; MemoryCRM for demo/tests."""
from __future__ import annotations

import os

import requests

from .qualifier import Qualification


class MemoryCRM:
    def __init__(self):
        self.contacts: dict[str, dict] = {}
        self.notes: list[dict] = []

    def upsert_lead(self, lead: dict, q: Qualification) -> str:
        cid = lead["email"].lower()
        self.contacts[cid] = {**lead, "ai_lead_score": q.score, "ai_lead_tier": q.tier}
        self.notes.append({"contact": cid, "body": format_note(q)})
        return cid


class HubSpotCRM:
    """Upserts by email. Create two custom contact properties first: ai_lead_score (number), ai_lead_tier (text)."""

    BASE = "https://api.hubapi.com"

    def __init__(self, token: str | None = None, session: requests.Session | None = None):
        self.s = session or requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token or os.environ['HUBSPOT_TOKEN']}", "Content-Type": "application/json"})

    def upsert_lead(self, lead: dict, q: Qualification) -> str:
        first, _, last = (lead.get("name") or "").partition(" ")
        props = {
            "email": lead["email"], "firstname": first, "lastname": last, "phone": lead.get("phone", ""),
            "company": lead.get("company", ""), "jobtitle": lead.get("job_title", ""),
            "ai_lead_score": str(q.score), "ai_lead_tier": q.tier,
            "hs_lead_status": "NEW" if q.tier != "spam" else "UNQUALIFIED",
        }
        r = self.s.post(f"{self.BASE}/crm/v3/objects/contacts/batch/upsert",
                        json={"inputs": [{"idProperty": "email", "id": lead["email"], "properties": props}]}, timeout=30)
        r.raise_for_status()
        cid = r.json()["results"][0]["id"]
        self.s.post(f"{self.BASE}/crm/v3/objects/notes", json={
            "properties": {"hs_note_body": format_note(q), "hs_timestamp": _now_ms()},
            "associations": [{"to": {"id": cid}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]}],
        }, timeout=30).raise_for_status()
        return cid


def _now_ms() -> int:
    from datetime import datetime, timezone

    return int(datetime.now(timezone.utc).timestamp() * 1000)


def format_note(q: Qualification) -> str:
    lines = [f"AI lead score: {q.score}/100 ({q.tier.upper()})", f"Summary: {q.summary}", f"Next step: {q.next_step}", "Why:"]
    lines += [f"- {r}" for r in q.reasons]
    return "\n".join(lines)
