# AI Lead Qualification + CRM Sync

**Know which leads to call first, and send a personal reply to every one of them in minutes, not days.** Every enquiry from your website, ads or email is scored 0–100 by AI against your ideal customer profile, saved to your CRM with the reasoning attached, and gets a tailored follow-up email drafted for you. A human approves (or edits) each email with one click before it goes out.

Built by [ThinkAIWorks](https://thinkaiworks.com).

## The flow

```
Form / ad / email
      │  POST /intake
      ▼
AI qualifies: budget · need · timeline · authority  →  score 0–100, hot / warm / cold / spam
      │
      ├─▶ CRM (HubSpot): contact upserted, score + tier set, note with the "why"
      │
      └─▶ Approval queue: personalised follow-up drafted
                │  rep reviews in the browser: edit → Approve & send / Reject
                ▼
           Sent via Gmail/Outlook (n8n or Make webhook) or SMTP
```

## Why teams use it

- **Hot leads first.** The queue is sorted by score, so the $6k "need it ASAP" enquiry is at the top, not buried under spam.
- **Spam filtered out** before anyone wastes time on it (SEO pitches, job applications, vendors).
- **Explainable scores.** Every lead gets a breakdown and plain-English reasons in the CRM.
- **Human in the loop.** Nothing is emailed without approval.
- **Works without AI too.** A built-in rules scorer runs when no API key is set, and takes over automatically if the AI call fails, so no lead is ever lost.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env            # optional: ANTHROPIC_API_KEY or OPENAI_API_KEY, HUBSPOT_TOKEN
python wsgi.py
```

Send a test lead:

```bash
curl -X POST localhost:5000/intake -H 'Content-Type: application/json' -d '{
  "name":"Rachel Green","email":"rachel@dentalgroup.com","company":"Green Dental","job_title":"Owner",
  "message":"We need to automate patient follow-ups. Budget around $6,000, want it live ASAP."}'
```

Then open `http://localhost:5000/?key=YOUR_ADMIN_KEY` to review and approve.

## Connect your tools

| What | How |
|---|---|
| **Lead sources** | Point a website form, n8n, Make, Zapier or Facebook Lead Ads at `POST /intake` (header `x-webhook-secret`) |
| **CRM** | HubSpot private app token. Create contact properties `ai_lead_score` (number) and `ai_lead_tier` (text) |
| **Sending** | `SEND_WEBHOOK_URL` → an n8n/Make flow that sends via Gmail or Outlook, or SMTP settings |
| **Your ICP** | Describe your ideal customer in a text file and set `ICP_FILE` |

## API

| Method | Path | |
|---|---|---|
| `POST` | `/intake` | Qualify a lead, sync to CRM, queue a draft |
| `GET` | `/queue?status=pending` | Drafts awaiting review |
| `POST` | `/queue/{id}/approve` | Optional `{subject, body}` edits, then send |
| `POST` | `/queue/{id}/reject` | Discard the draft |
| `GET` | `/` | Review page |

## Tests

```bash
pytest -q
```

## Stack

Python · Flask · Claude / OpenAI (JSON output) · HubSpot CRM API · SQLite · n8n / Make webhooks
