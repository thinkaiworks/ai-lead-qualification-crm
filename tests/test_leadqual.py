import pytest

from leadqual.app import create_app
from leadqual.crm import MemoryCRM
from leadqual.drafts import draft_followup
from leadqual.qualifier import qualify_rules
from leadqual.queue import ApprovalQueue

HOT = {
    "name": "Rachel Green", "email": "rachel@dentalgroup.com", "company": "Green Dental Group", "job_title": "Owner",
    "message": "We need to automate our patient follow-ups and appointment reminders. We're losing bookings every week. "
               "Budget is around $6,000 and we want this live ASAP.",
}
COLD = {"name": "Tim", "email": "tim@gmail.com", "message": "just curious what you do"}
SPAM = {"name": "Bob", "email": "bob@seo.biz", "message": "We can offer you SEO services and guest post backlinks"}


@pytest.fixture(autouse=True)
def no_keys(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "HUBSPOT_TOKEN", "SEND_WEBHOOK_URL", "SMTP_HOST", "WEBHOOK_SECRET", "ADMIN_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_rules_scoring_tiers():
    hot = qualify_rules(HOT)
    assert hot.tier == "hot" and hot.score >= 70
    assert hot.breakdown["budget_score"] == 25
    assert qualify_rules(COLD).tier == "cold"
    assert qualify_rules(SPAM).tier == "spam"


def test_budget_parsing_with_k():
    q = qualify_rules({"email": "a@b.co", "message": "need help, budget $3k"})
    assert q.breakdown["budget_score"] == 18


def test_draft_for_hot_lead_and_none_for_spam():
    d = draft_followup(HOT, qualify_rules(HOT), sender="Ali", calendar="https://cal.com/ali")
    assert d["subject"].startswith("Quick call")
    assert "Hi Rachel" in d["body"] and "https://cal.com/ali" in d["body"]
    assert draft_followup(SPAM, qualify_rules(SPAM)) is None


def test_queue_orders_by_score_and_blocks_double_decision():
    q = ApprovalQueue(":memory:")
    a = q.add(COLD, qualify_rules(COLD).to_dict(), {"subject": "s", "body": "b"})
    b = q.add(HOT, qualify_rules(HOT).to_dict(), {"subject": "s", "body": "b"})
    assert [d["id"] for d in q.list()] == [b, a]
    q.decide(a, "rejected")
    with pytest.raises(ValueError):
        q.decide(a, "approved")


def test_end_to_end_intake_review_approve(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", "k")
    crm = MemoryCRM()
    app = create_app(crm=crm, queue=ApprovalQueue(":memory:"))
    c = app.test_client()

    r = c.post("/intake", json=HOT)
    assert r.status_code == 201
    body = r.get_json()
    assert body["qualification"]["tier"] == "hot"
    assert crm.contacts["rachel@dentalgroup.com"]["ai_lead_tier"] == "hot"
    assert "AI lead score" in crm.notes[0]["body"]

    assert c.post("/intake", json=SPAM).get_json()["draft_id"] is None
    assert c.post("/intake", json={"name": "x"}).status_code == 422

    assert c.get("/queue").status_code == 401
    pending = c.get("/queue", headers={"x-admin-key": "k"}).get_json()
    assert len(pending) == 1
    assert b"Rachel Green" in c.get("/?key=k").data

    r = c.post(f"/queue/{body['draft_id']}/approve", headers={"x-admin-key": "k"}, json={"subject": "Edited subject"})
    assert r.get_json() == {"status": "sent", "channel": "logged"}
    assert c.post(f"/queue/{body['draft_id']}/approve", headers={"x-admin-key": "k"}).status_code == 409
