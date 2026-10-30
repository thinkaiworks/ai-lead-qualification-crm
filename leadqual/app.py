"""Flask app: lead intake webhook + approval queue (API and a simple review page)."""
from __future__ import annotations

import hmac
import os

from flask import Flask, abort, jsonify, render_template, request

from .crm import HubSpotCRM, MemoryCRM
from .drafts import draft_followup
from .llm import provider
from .qualifier import ICP_DEFAULT, qualify
from .queue import ApprovalQueue
from .sender import send_email

REQUIRED = ("email",)


def create_app(crm=None, queue: ApprovalQueue | None = None) -> Flask:
    app = Flask(__name__)
    crm = crm or (HubSpotCRM() if os.getenv("HUBSPOT_TOKEN") else MemoryCRM())
    queue = queue or ApprovalQueue(os.getenv("DB_PATH", "data/leads.db"))
    icp = open(os.environ["ICP_FILE"]).read() if os.getenv("ICP_FILE") else ICP_DEFAULT
    secret = os.getenv("WEBHOOK_SECRET", "")
    admin_key = os.getenv("ADMIN_KEY", "")

    def require_admin():
        if admin_key and not hmac.compare_digest(request.headers.get("x-admin-key", request.args.get("key", "")), admin_key):
            abort(401)

    @app.get("/health")
    def health():
        return {"status": "ok", "scoring": provider()}

    @app.post("/intake")
    def intake():
        if secret and not hmac.compare_digest(request.headers.get("x-webhook-secret", ""), secret):
            abort(401)
        lead = request.get_json(silent=True) or request.form.to_dict()
        missing = [f for f in REQUIRED if not lead.get(f)]
        if missing:
            return jsonify(error=f"missing: {', '.join(missing)}"), 422
        q = qualify(lead, icp)
        contact_id = crm.upsert_lead(lead, q)
        draft = draft_followup(lead, q, sender=os.getenv("SENDER_NAME", "The Team"), calendar=os.getenv("CALENDAR_URL", "https://cal.example.com/intro"))
        draft_id = queue.add(lead, q.to_dict(), draft) if draft else None
        return jsonify(contact_id=contact_id, qualification=q.to_dict(), draft_id=draft_id), 201

    @app.get("/queue")
    def list_queue():
        require_admin()
        return jsonify(queue.list(request.args.get("status", "pending") or None))

    @app.post("/queue/<int:draft_id>/approve")
    def approve(draft_id: int):
        require_admin()
        edits = request.get_json(silent=True) or {}
        try:
            d = queue.decide(draft_id, "approved", edits.get("subject"), edits.get("body"))
        except KeyError:
            abort(404)
        except ValueError as e:
            return jsonify(error=str(e)), 409
        channel = send_email(d["lead"]["email"], d["subject"], d["body"])
        d = queue.decide(draft_id, "sent")
        return jsonify(status=d["status"], channel=channel)

    @app.post("/queue/<int:draft_id>/reject")
    def reject(draft_id: int):
        require_admin()
        try:
            return jsonify(queue.decide(draft_id, "rejected"))
        except KeyError:
            abort(404)
        except ValueError as e:
            return jsonify(error=str(e)), 409

    @app.get("/")
    def review_page():
        require_admin()
        return render_template("review.html", drafts=queue.list("pending"), key=request.args.get("key", ""))

    return app
