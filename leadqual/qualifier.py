"""Score an inbound enquiry: budget, need, timeline, authority -> 0-100 score and hot/warm/cold tier."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from . import llm

ICP_DEFAULT = """We are a B2B agency. Ideal clients: service businesses with 5-200 staff,
budget of $2,000+ for a project, wanting results within 3 months. Not a fit: students, job seekers,
people selling to us, budgets under $500."""

SYSTEM = """You qualify inbound sales leads against the company's ideal customer profile (ICP).
Return ONLY a JSON object with these keys:
  budget_score (0-25), need_score (0-25), timeline_score (0-25), authority_score (0-25),
  tier ("hot" | "warm" | "cold" | "spam"),
  summary (one sentence describing what they want),
  reasons (array of short strings explaining the score),
  next_step (one short sentence: what the sales rep should do).
Be strict: missing information scores low, never invent facts. Spam, job applications and vendors pitching us are "spam"."""


@dataclass
class Qualification:
    score: int
    tier: str
    summary: str
    reasons: list[str]
    next_step: str
    breakdown: dict
    method: str

    def to_dict(self) -> dict:
        return asdict(self)


def tier_for(score: int) -> str:
    return "hot" if score >= 70 else "warm" if score >= 40 else "cold"


def qualify(lead: dict, icp: str = ICP_DEFAULT) -> Qualification:
    if llm.provider() != "rules":
        try:
            return _qualify_llm(lead, icp)
        except Exception as exc:  # fall back rather than lose the lead
            q = qualify_rules(lead)
            q.reasons.append(f"AI scoring failed, used rules: {exc.__class__.__name__}")
            return q
    return qualify_rules(lead)


def _qualify_llm(lead: dict, icp: str) -> Qualification:
    user = f"ICP:\n{icp}\n\nLEAD:\n" + "\n".join(f"{k}: {v}" for k, v in lead.items() if v)
    d = llm.complete_json(SYSTEM, user)
    parts = {k: max(0, min(25, int(d.get(k, 0)))) for k in ("budget_score", "need_score", "timeline_score", "authority_score")}
    score = sum(parts.values())
    tier = d.get("tier") if d.get("tier") == "spam" else tier_for(score)
    return Qualification(score, tier, d.get("summary", ""), list(d.get("reasons", [])), d.get("next_step", ""), parts, llm.provider())


MONEY = re.compile(r"\$\s?(\d[\d,]*)(\s?k)?|(\d[\d,]*)\s?(usd|dollars)", re.I)
URGENT = re.compile(r"\b(asap|urgent|this week|immediately|right away|next week|this month)\b", re.I)
SOON = re.compile(r"\b(within (a|1|one|2|two|3|three) months?|this quarter|q[1-4]|soon)\b", re.I)
SPAM = re.compile(r"\b(seo services|guest post|backlinks|hire me|my resume|job application|crypto investment|we can offer you)\b", re.I)
DECIDER = re.compile(r"\b(owner|founder|ceo|director|head of|vp|president|partner|manager)\b", re.I)
NEED = re.compile(r"\b(need|looking for|want to|help with|automate|build|struggling|losing)\b", re.I)


def _budget(text: str) -> int | None:
    best = None
    for m in MONEY.finditer(text):
        raw = (m.group(1) or m.group(3) or "0").replace(",", "")
        val = int(raw) * (1000 if m.group(2) else 1)
        best = max(best or 0, val)
    return best


def qualify_rules(lead: dict) -> Qualification:
    text = " ".join(str(v) for v in lead.values() if v)
    if SPAM.search(text):
        return Qualification(0, "spam", "Looks like spam or a sales pitch.", ["Matched spam pattern"], "Ignore.", {}, "rules")

    reasons = []
    budget = _budget(f"{lead.get('budget', '')} {lead.get('message', '')}")
    b = 25 if budget and budget >= 5000 else 18 if budget and budget >= 2000 else 8 if budget and budget >= 500 else 0
    reasons.append(f"Budget ${budget:,}" if budget else "No budget mentioned")

    msg = str(lead.get("message", ""))
    n = 20 if NEED.search(msg) and len(msg) > 60 else 10 if NEED.search(msg) else 3
    reasons.append("Clear need described" if n >= 20 else "Vague need")

    t = 25 if URGENT.search(text) else 15 if SOON.search(text) else 5
    reasons.append({25: "Urgent timeline", 15: "Near-term timeline", 5: "No timeline"}[t])

    role = f"{lead.get('job_title', '')} {msg}"
    a = 25 if DECIDER.search(role) else 15 if lead.get("company") else 5
    reasons.append("Decision maker" if a == 25 else "Authority unclear")

    breakdown = {"budget_score": b, "need_score": n, "timeline_score": t, "authority_score": a}
    score = sum(breakdown.values())
    tier = tier_for(score)
    summary = (msg[:140] + "…") if len(msg) > 140 else msg
    next_step = {"hot": "Call within 1 hour and book a discovery call.", "warm": "Send a tailored follow-up today with a case study.", "cold": "Add to nurture sequence."}[tier]
    return Qualification(score, tier, summary, reasons, next_step, breakdown, "rules")
