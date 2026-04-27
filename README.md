# Freelancing Bot

`freelancing-bot` is an adaptation of the existing AgentBot architecture to find
freelance leads across LinkedIn plus other platforms and initiate outreach.

It focuses on people and organisations likely to need **automation**, **AI/ML** and
**full-stack development** help based on your portfolio profile:

- Portfolio: https://portfolio-bhandakkarparth.netlify.app/

## What it includes

- Browser automation from `browser/engine.py`.
- LLM-powered lead qualification + message drafting (optional).
- Multi-source lead discovery: LinkedIn profiles, LinkedIn buyer-intent posts, Upwork jobs, and Clutch via search fallback.
- Buyer-intent ranking that gives the highest scores to posts/snippets where someone is actively asking for a freelancer, developer, project help, or paid work in your service area.
- Outreach flow for messaging and connection requests.
- CSV-based lead storage.
- FastAPI control API (`server.py`).
- Single server entrypoint (`main.py`) for the dashboard and API.

## Folder structure

- `browser/` - browser engine and LinkedIn auth.
- `linkedin/` - client search logic.
- `llm/` - LLM client and prompts.
- `models/` - Pydantic schemas.
- `outreach/` - messaging and connection note flow.
- `utils/` - helpers, logging, CSV persistence, and Google Sheet sync (`Outreach` sheet).
- `data/` - leads, report, and screenshots.

## Setup

1. Install project dependencies (same base environment as existing AgentBot).
2. Create `.env` with credentials for LinkedIn and optional LLM provider.
3. Start the server:

```bash
python main.py
```

Optional server flags:

```bash
python main.py --host 0.0.0.0 --port 8080 --headless
```

## Dashboard

Open the control UI at:

`http://localhost:8080/dashboard`

Controls include:

- trigger `discover` / `outreach` / `campaign`
- choose source mix (LinkedIn, LinkedIn Posts, Upwork, Clutch)
- pause / resume / stop
- live status polling
- recent result summaries and runtime state

## API endpoints

- `GET /health`
- `GET /modes`
- `GET /status`
- `GET /dashboard`
- `POST /discover` body: `{ "max_results": 30, "sources": "linkedin,linkedin_posts,upwork,clutch", "headless": false }`
- `POST /outreach` body: `{ "max_results": 20, "headless": false }`
- `POST /campaign` body: `{ "discovery_limit": 50, "outreach_limit": 20, "sources": "linkedin,linkedin_posts,upwork,clutch", "headless": false }`
- Google Sheets integration uses `.env` keys: `GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_FILE`, and
  `GOOGLE_OUTREACH_SHEET_NAME` (auto-creates headers in sheet `Outreach` if missing).
- `POST /pause`
- `POST /resume`
- `POST /stop`

## Safety notes

- Add delays and run in modest volumes to respect LinkedIn terms.
- Keep messages concise and relevant to avoid account restrictions.
- Review and adjust message templates in `.env` before production runs.

