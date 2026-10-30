"""Send an approved email: via webhook (n8n/Make -> Gmail/Outlook), SMTP, or log only."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

import requests


def send_email(to: str, subject: str, body: str) -> str:
    hook = os.getenv("SEND_WEBHOOK_URL")
    if hook:
        requests.post(hook, json={"to": to, "subject": subject, "body": body}, timeout=30).raise_for_status()
        return "webhook"
    host = os.getenv("SMTP_HOST")
    if host:
        msg = EmailMessage()
        msg["From"] = os.environ["SMTP_FROM"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as s:
            s.starttls()
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.send_message(msg)
        return "smtp"
    return "logged"
