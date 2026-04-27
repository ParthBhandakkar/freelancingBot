"""HTTP API and dashboard for running the freelancing bot."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from browser.engine import BrowserEngine
from config import settings
from models.schemas import FreelanceClientLead, OutreachResult, OutreachResultStatus
from orchestrator import FreelancingOrchestrator

app = FastAPI(title="Freelancing Bot API", version="3.0.0")
orchestrator = FreelancingOrchestrator()
_DASHBOARD_PATH = Path(__file__).resolve().with_name("dashboard.html")


@dataclass
class ControlState:
    active_task: asyncio.Task | None = None
    active_operation: str = ""
    last_error: str = ""
    last_result: dict[str, Any] = field(default_factory=dict)
    last_started_at: str = ""
    last_finished_at: str = ""

    def is_busy(self) -> bool:
        return self.active_task is not None and not self.active_task.done()


control_state = ControlState()


def _parse_sources(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


class DiscoveryRequest(BaseModel):
    max_results: Optional[int] = None
    headless: bool | None = None
    sources: Optional[str] = None


class OutreachRequest(BaseModel):
    max_results: Optional[int] = None
    headless: bool | None = None


class CampaignRequest(BaseModel):
    discovery_limit: Optional[int] = None
    outreach_limit: Optional[int] = None
    sources: Optional[str] = None
    headless: bool | None = None


def _apply_headless(req_headless: bool | None) -> None:
    if req_headless is not None:
        settings.headless = req_headless


def _normalise_sources(req_sources: str | None) -> list[str]:
    parsed = _parse_sources(req_sources)
    if parsed:
        return parsed
    return settings.discover_platform_list


def _available_modes() -> list[dict[str, Any]]:
    return [
        {
            "id": "discover",
            "label": "Scrape Leads",
            "description": "Find and score client leads across LinkedIn, LinkedIn posts, Upwork, and Clutch.",
            "sends_outreach": False,
            "browser_required": False,
        },
        {
            "id": "connect",
            "label": "Connect",
            "description": "Open LinkedIn leads and send connection requests where the profile is not first-degree yet.",
            "sends_outreach": True,
            "browser_required": True,
        },
        {
            "id": "message",
            "label": "Check And Message",
            "description": "Revisit requested or connected leads and only send messages once LinkedIn shows first-degree access.",
            "sends_outreach": True,
            "browser_required": True,
        },
        {
            "id": "outreach",
            "label": "Combined Outreach",
            "description": "Message existing first-degree connections and send connection requests to everyone else.",
            "sends_outreach": True,
            "browser_required": True,
        },
        {
            "id": "campaign",
            "label": "Full Campaign",
            "description": "Run discovery first and then the combined outreach pass in the same session.",
            "sends_outreach": True,
            "browser_required": True,
        },
    ]


def _status_payload() -> dict[str, Any]:
    return {
        "bot": orchestrator.status(),
        "control": {
            "busy": control_state.is_busy(),
            "active_operation": control_state.active_operation,
            "last_error": control_state.last_error,
            "last_result": control_state.last_result,
            "last_started_at": control_state.last_started_at,
            "last_finished_at": control_state.last_finished_at,
        },
        "runtime": {
            "browser_available": BrowserEngine.is_available(),
            "headless": settings.headless,
            "sources": settings.discover_platform_list,
        },
    }


async def _run_operation(name: str, runner: Awaitable[Any]) -> None:
    control_state.active_operation = name
    control_state.last_error = ""
    control_state.last_result = {}
    control_state.last_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    control_state.last_finished_at = ""
    try:
        result = await runner
        control_state.last_result = _summarize_result(name, result)
    except Exception as exc:
        control_state.last_error = str(exc)
        control_state.last_result = {
            "operation": name,
            "success": False,
            "error": str(exc),
        }
    finally:
        control_state.last_finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        control_state.active_operation = ""
        control_state.active_task = None


def _summarize_result(name: str, result: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "operation": name,
        "success": True,
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if isinstance(result, list) and result and isinstance(result[0], FreelanceClientLead):
        leads = result
        summary.update(
            {
                "count": len(leads),
                "candidate_count": len([lead for lead in leads if lead.status.value == "candidate"]),
                "top_leads": [
                    {
                        "name": lead.full_name,
                        "score": lead.fit_score,
                        "source": lead.source_platform,
                        "profile_url": lead.profile_url,
                        "post_link": lead.post_link,
                    }
                    for lead in leads[:5]
                ],
            }
        )
    elif isinstance(result, list) and result and isinstance(result[0], OutreachResult):
        outputs = result
        summary.update(
            {
                "count": len(outputs),
                "messages_sent": len(
                    [item for item in outputs if item.status == OutreachResultStatus.MESSAGE_SENT]
                ),
                "connect_requested": len(
                    [item for item in outputs if item.status == OutreachResultStatus.CONNECT_REQUESTED]
                ),
                "connected": len(
                    [item for item in outputs if item.status == OutreachResultStatus.CONNECTED]
                ),
                "skipped": len([item for item in outputs if item.status == OutreachResultStatus.SKIPPED]),
                "failed": len(
                    [
                        item
                        for item in outputs
                        if item.status in {OutreachResultStatus.FAILED, OutreachResultStatus.BLOCKED}
                    ]
                ),
                "recent_actions": [
                    {
                        "name": item.lead.full_name,
                        "status": item.status.value,
                        "action": item.action_taken,
                        "profile_url": item.lead.profile_url,
                    }
                    for item in outputs[:5]
                ],
            }
        )
    else:
        summary["result"] = result
    return summary


def _guard_operation_start(name: str) -> None:
    if control_state.is_busy():
        raise HTTPException(
            status_code=409,
            detail=f"Another operation is already running: {control_state.active_operation}",
        )
    if name in {"connect", "message", "outreach", "campaign"} and not BrowserEngine.is_available():
        raise HTTPException(
            status_code=400,
            detail="LinkedIn browser automation requires the local agent-browser runtime to be available.",
        )


def _launch_operation(name: str, runner_factory: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    _guard_operation_start(name)
    control_state.active_task = asyncio.create_task(_run_operation(name, runner_factory()))
    return {
        "accepted": True,
        "operation": name,
        "message": f"{name} started",
        "status": _status_payload(),
    }


@app.get("/", response_class=RedirectResponse)
def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/modes")
def modes() -> dict[str, Any]:
    return {"modes": _available_modes()}


@app.get("/status")
def status() -> dict[str, Any]:
    return _status_payload()


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    if not _DASHBOARD_PATH.exists():
        raise HTTPException(status_code=500, detail="dashboard.html is missing")
    return _DASHBOARD_PATH.read_text(encoding="utf-8")


@app.post("/discover", status_code=202)
async def discover(req: DiscoveryRequest) -> dict[str, Any]:
    _apply_headless(req.headless)
    return _launch_operation(
        "discover",
        lambda: orchestrator.discover(
            req.max_results,
            platform_sources=_normalise_sources(req.sources),
        ),
    )


@app.post("/connect", status_code=202)
async def connect(req: OutreachRequest) -> dict[str, Any]:
    _apply_headless(req.headless)
    return _launch_operation("connect", lambda: orchestrator.connecting(req.max_results))


@app.post("/message", status_code=202)
async def message(req: OutreachRequest) -> dict[str, Any]:
    _apply_headless(req.headless)
    return _launch_operation("message", lambda: orchestrator.messaging(req.max_results))


@app.post("/outreach", status_code=202)
async def outreach(req: OutreachRequest) -> dict[str, Any]:
    _apply_headless(req.headless)
    return _launch_operation("outreach", lambda: orchestrator.outreaching(req.max_results))


@app.post("/campaign", status_code=202)
async def campaign(req: CampaignRequest) -> dict[str, Any]:
    _apply_headless(req.headless)
    return _launch_operation(
        "campaign",
        lambda: orchestrator.run_campaign(
            req.discovery_limit,
            req.outreach_limit,
            discovery_sources=_normalise_sources(req.sources),
        ),
    )


@app.post("/pause")
async def pause_bot() -> dict[str, Any]:
    await orchestrator.pause()
    return _status_payload()


@app.post("/resume")
async def resume_bot() -> dict[str, Any]:
    await orchestrator.resume()
    return _status_payload()


@app.post("/stop")
async def stop_bot() -> dict[str, Any]:
    await orchestrator.stop()
    return _status_payload()
