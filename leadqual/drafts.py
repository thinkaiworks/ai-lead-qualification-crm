"""Draft a personalised follow-up email for a human to approve before it's sent."""
from __future__ import annotations

from . import llm
from .qualifier import Qualification

SYSTEM = """You write short, warm, specific sales follow-up emails for a human rep to review.
Rules: under 120 words, reference what the lead actually asked for, one clear call to action,
no hype, no made-up facts, no prices unless the lead mentioned one. Sign off as {sender}.
Return ONLY JSON: {{"subject": "...", "body": "..."}}"""

TEMPLATES = {
    "hot": ("Quick call about {topic}?",
            "Hi {first},\n\nThanks for reaching out about {topic}. It sounds like timing matters, so I'd love to get you answers fast.\n\n"
            "Do you have 15 minutes tomorrow for a quick call? Here's my calendar: {calendar}\n\nBest,\n{sender}"),
    "warm": ("Re: {topic}",
             "Hi {first},\n\nThanks for getting in touch about {topic}. I've attached a short example of how we've handled something similar.\n\n"
             "Would a short call next week be useful? You can grab a time here: {calendar}\n\nBest,\n{sender}"),
    "cold": ("Thanks for reaching out",
             "Hi {first},\n\nThanks for your message about {topic}. I'll send over a few resources that should help as you plan.\n\n"
             "Whenever you're ready to talk, just reply here.\n\nBest,\n{sender}"),
}


def draft_followup(lead: dict, q: Qualification, sender: str = "The Team", calendar: str = "https://cal.example.com/intro") -> dict | None:
    if q.tier == "spam":
        return None
    first = (lead.get("name") or "there").split()[0]
    if llm.provider() != "rules":
        try:
            user = f"Lead: {lead}\nQualification: tier={q.tier}, summary={q.summary}, next_step={q.next_step}\nCalendar link: {calendar}"
            d = llm.complete_json(SYSTEM.format(sender=sender), user)
            return {"subject": d["subject"], "body": d["body"], "method": llm.provider()}
        except Exception:
            pass
    topic = (q.summary or "your project").rstrip(".…").lower()
    topic = topic if len(topic) < 60 else "your project"
    subj, body = TEMPLATES[q.tier]
    vals = {"first": first, "topic": topic, "sender": sender, "calendar": calendar}
    return {"subject": subj.format(**vals), "body": body.format(**vals), "method": "template"}
