"""Top-level orchestration for the freelancing bot."""
from __future__ import annotations

from datetime import datetime
import json
from typing import Literal

from loguru import logger

from browser.engine import BrowserEngine
from config import DATA_DIR, settings
from linkedin.auth import LinkedInAuth
from linkedin.client_search import LinkedInClientSearcher
from llm.client import llm_client
from platforms.discovery import PlatformDiscoveryService
from models.schemas import BotState, CampaignStats, FreelanceClientLead, OutreachResult, OutreachResultStatus, ProspectStatus
from outreach.messenger import ClientOutreachMessenger
from utils.csv_exporter import append_leads, load_pending_leads, update_lead_status
from utils.sheets_integration import OutreachSheetStore
from utils.helpers import human_delay
from utils.logger import setup_logger


class FreelancingOrchestrator:
    def __init__(self) -> None:
        self.browser = BrowserEngine()
        self.browser_started = False
        self.auth = LinkedInAuth(self.browser)
        self.searcher = LinkedInClientSearcher(self.browser)
        self.platform_searcher = PlatformDiscoveryService(self.browser)
        self.messenger = ClientOutreachMessenger(self.browser)
        self.sheet_store = OutreachSheetStore()

        self.state = BotState.IDLE
        self.stats = CampaignStats()
        self._stop_requested = False
        self._pause_requested = False

    async def start(self, *, headless: bool | None = None, require_linkedin_login: bool = False) -> None:
        if headless is not None:
            settings.headless = headless

        setup_logger()
        self._stop_requested = False
        self.state = BotState.STARTING
        self.stats = CampaignStats(session_start=datetime.now())

        if not BrowserEngine.is_available():
            if require_linkedin_login:
                raise RuntimeError(
                    "LinkedIn login requires the local agent-browser checkout, but it is unavailable."
                )
            logger.warning("Browser automation is unavailable; continuing with browserless discovery.")
            self.browser_started = False
            self.state = BotState.IDLE
            return

        await self.browser.start()
        self.browser_started = True
        if require_linkedin_login:
            logged = await self.auth.ensure_logged_in()
            if not logged:
                raise RuntimeError("LinkedIn login failed. Please verify credentials and challenge flow.")
        self.state = BotState.IDLE

    async def stop(self, save_report: bool = True, requested: bool = True) -> None:
        self._stop_requested = requested
        self._pause_requested = False
        if requested:
            self.state = BotState.STOPPED
        if save_report:
            self.stats.session_end = datetime.now()
            self._write_session_report()
        if self.browser_started:
            await self.browser.stop()
            self.browser_started = False
        if not requested:
            self._stop_requested = False

    async def pause(self) -> None:
        self._pause_requested = True
        self.state = BotState.PAUSED

    async def resume(self) -> None:
        self._pause_requested = False
        if self.state == BotState.PAUSED:
            self.state = BotState.IDLE

    async def discover(
        self,
        max_results: int | None = None,
        platform_sources: list[str] | None = None,
    ) -> list[FreelanceClientLead]:
        logger.info("Starting client discovery run")
        await self.start(require_linkedin_login=False)
        try:
            return await self._discover_impl(max_results=max_results, platform_sources=platform_sources)
        finally:
            await self.stop(requested=False)
            self.state = BotState.IDLE

    async def outreaching(self, max_results: int | None = None) -> list[OutreachResult]:
        await self.start(require_linkedin_login=True)
        try:
            outputs = await self._outreach_impl(max_results=max_results, mode="combined")
            self.stats.session_end = datetime.now()
            self._write_session_report()
            return outputs
        finally:
            await self.stop(save_report=False, requested=False)
            self.state = BotState.IDLE

    async def connecting(self, max_results: int | None = None) -> list[OutreachResult]:
        await self.start(require_linkedin_login=True)
        try:
            outputs = await self._outreach_impl(max_results=max_results, mode="connect")
            self.stats.session_end = datetime.now()
            self._write_session_report()
            return outputs
        finally:
            await self.stop(save_report=False, requested=False)
            self.state = BotState.IDLE

    async def messaging(self, max_results: int | None = None) -> list[OutreachResult]:
        await self.start(require_linkedin_login=True)
        try:
            outputs = await self._outreach_impl(max_results=max_results, mode="message")
            self.stats.session_end = datetime.now()
            self._write_session_report()
            return outputs
        finally:
            await self.stop(save_report=False, requested=False)
            self.state = BotState.IDLE

    async def run_campaign(
        self,
        discovery_limit: int | None = None,
        outreach_limit: int | None = None,
        discovery_sources: list[str] | None = None,
    ) -> list[OutreachResult]:
        await self.start(require_linkedin_login=True)
        try:
            await self._discover_impl(max_results=discovery_limit, platform_sources=discovery_sources)
            await human_delay(settings.search_delay_min, settings.search_delay_max)
            outputs = await self._outreach_impl(max_results=outreach_limit, mode="combined")
            self.stats.session_end = datetime.now()
            self._write_session_report()
            logger.info(
                "Campaign finished: discovered {}, outreached {}",
                self.stats.discovered,
                self.stats.outreached,
            )
            return outputs
        finally:
            await self.stop(save_report=False, requested=False)
            self.state = BotState.IDLE

    async def _discover_impl(
        self,
        *,
        max_results: int | None = None,
        platform_sources: list[str] | None = None,
    ) -> list[FreelanceClientLead]:
        self.state = BotState.DISCOVERING
        discovered: list[FreelanceClientLead] = []
        requested_limit = max_results or settings.max_discovery_results
        enabled = set(platform_sources or settings.discover_platform_list)

        if "linkedin" in enabled:
            linkedin_leads = await self.searcher.discover_clients(max_results=requested_limit)
            discovered.extend(linkedin_leads)

        if enabled - {"linkedin"}:
            external = await self.platform_searcher.discover(
                max_results=requested_limit,
                platform_sources=list(enabled - {"linkedin"}),
            )
            discovered.extend(external)

        leads = self._dedupe_and_rank(discovered, limit=requested_limit)
        leads = await self._score_discovered_leads(leads)
        leads = self._dedupe_and_rank(leads, limit=requested_limit)

        added, _ = append_leads(leads, settings.lead_store_file)
        sheet_added = self.sheet_store.append_leads(leads)
        logger.info("Sheets outreach rows added: {}", sheet_added)
        self.stats.discovered = len(leads)
        self.stats.candidate = len([lead for lead in leads if lead.status == ProspectStatus.CANDIDATE])
        logger.info("Discovered {} candidates; {} added to store", self.stats.candidate, added)
        return leads

    async def _score_discovered_leads(
        self,
        leads: list[FreelanceClientLead],
    ) -> list[FreelanceClientLead]:
        if not settings.has_llm_key or not await llm_client.is_available():
            return leads

        scored: list[FreelanceClientLead] = []
        for lead in leads:
            if lead.source_platform.lower() == "linkedin":
                scored.append(await self.searcher.score_with_llm(lead))
            else:
                scored.append(lead)
        return scored

    async def _outreach_impl(
        self,
        *,
        max_results: int | None = None,
        mode: Literal["combined", "connect", "message"] = "combined",
    ) -> list[OutreachResult]:
        self.state = BotState.OUTREACHING
        leads = self._load_outreach_leads(max_results=max_results, mode=mode)
        outputs: list[OutreachResult] = []

        for lead in leads:
            if self._stop_requested:
                break
            while self._pause_requested:
                await self._pause_loop()

            if lead.source_platform.lower() != "linkedin":
                result = OutreachResult(
                    lead=lead,
                    status=OutreachResultStatus.SKIPPED,
                    action_taken="unsupported_source",
                    notes="Outreach flow currently supports LinkedIn messaging only. Kept for manual follow-up.",
                )
                outputs.append(result)
                self.stats.results.append(result)
                self.stats.skipped += 1
                self._update_stats_in_sheet(lead, OutreachResultStatus.SKIPPED, "unsupported_source", "skipped")
                update_lead_status(
                    lead.profile_url,
                    status=ProspectStatus.SKIPPED,
                    outreach_action=result.action_taken,
                    outreach_note=result.notes,
                    notes="Manual follow-up required for non-LinkedIn source.",
                )
                continue

            if mode == "connect":
                result = await self.messenger.send_connection_request(lead)
            elif mode == "message":
                result = await self.messenger.send_message_if_ready(lead)
            else:
                result = await self.messenger.reach_out_to_lead(lead)
            outputs.append(result)
            self.stats.results.append(result)
            self.stats.outreached += 1
            self._update_stats_in_sheet(
                lead,
                result.status,
                result.action_taken,
                result.notes,
                message_text=result.message_text,
            )

            if result.status == OutreachResultStatus.MESSAGE_SENT:
                self.stats.messages_sent += 1
                update_lead_status(
                    lead.profile_url,
                    status=ProspectStatus.MESSAGE_SENT,
                    outreach_action=result.action_taken,
                    outreach_note=result.message_text,
                    last_contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    notes=result.notes,
                )
            elif result.status == OutreachResultStatus.CONNECT_REQUESTED:
                self.stats.connect_requested += 1
                update_lead_status(
                    lead.profile_url,
                    status=ProspectStatus.CONNECT_REQUESTED,
                    outreach_action=result.action_taken,
                    outreach_note=result.message_text,
                    last_contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    notes=result.notes,
                )
            elif result.status == OutreachResultStatus.CONNECTED:
                self.stats.connected += 1
                update_lead_status(
                    lead.profile_url,
                    status=ProspectStatus.CONNECTED,
                    outreach_action=result.action_taken,
                    outreach_note=result.message_text,
                    last_contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    notes=result.notes,
                )
            elif result.status == OutreachResultStatus.SKIPPED:
                self.stats.skipped += 1
                update_lead_status(
                    lead.profile_url,
                    status=lead.status,
                    outreach_action=result.action_taken,
                    outreach_note=result.message_text,
                    notes=result.notes,
                )
            else:
                self.stats.failed += 1
                update_lead_status(
                    lead.profile_url,
                    status=ProspectStatus.FAILED,
                    outreach_action=result.action_taken,
                    outreach_note=result.message_text,
                    last_contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    notes=result.notes,
                )

            await human_delay(settings.outreach_delay_min, settings.outreach_delay_max)

        return outputs

    def _load_outreach_leads(
        self,
        *,
        max_results: int | None = None,
        mode: Literal["combined", "connect", "message"] = "combined",
    ) -> list[FreelanceClientLead]:
        if mode == "connect":
            status_values = [ProspectStatus.CANDIDATE, ProspectStatus.DISCOVERED]
        elif mode == "message":
            status_values = [ProspectStatus.CONNECT_REQUESTED, ProspectStatus.CONNECTED]
        else:
            status_values = [
                ProspectStatus.CANDIDATE,
                ProspectStatus.DISCOVERED,
                ProspectStatus.CONNECTED,
            ]
        leads = load_pending_leads(
            status_values,
            filename=settings.lead_store_file,
            min_score=0,
        )
        leads = [lead for lead in leads if lead.source_platform.lower() == "linkedin"]
        leads.sort(
            key=lambda lead: (
                lead.status != ProspectStatus.CONNECTED,
                -lead.fit_score,
                lead.discovered_at,
            )
        )
        return leads[: (max_results or settings.max_outreach_per_run)]

    def _dedupe_and_rank(
        self,
        leads: list[FreelanceClientLead],
        limit: int | None = None,
    ) -> list[FreelanceClientLead]:
        unique: list[FreelanceClientLead] = []
        seen: set[str] = set()
        for lead in leads:
            key = (lead.profile_url or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(lead)
        unique.sort(key=lambda item: item.fit_score, reverse=True)
        return unique[: limit or settings.max_discovery_results]

    def _update_stats_in_sheet(
        self,
        lead: FreelanceClientLead,
        status: OutreachResultStatus,
        action: str,
        notes: str = "",
        message_text: str = "",
    ) -> None:
        mapped_status = status.value
        self.sheet_store.update_status(
            lead.profile_url,
            status=mapped_status,
            action=action,
            contacted_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            message_text=message_text,
            notes=notes,
        )

    def status(self) -> dict:
        return {
            "state": self.state.value,
            "stop_requested": self._stop_requested,
            "pause_requested": self._pause_requested,
            "discovery_sources": settings.discover_platform_list,
            "stats": self._stats_dict(),
        }

    async def _pause_loop(self) -> None:
        await human_delay(0.5, 0.9)

    def _write_session_report(self) -> None:
        reports_dir = DATA_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_file = reports_dir / f"freelancing_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with report_file.open("w", encoding="utf-8") as f:
            json.dump(self._stats_dict(), f, ensure_ascii=False, indent=2, default=str)
        logger.info("Saved report to {}", report_file)

    def _stats_dict(self) -> dict:
        if hasattr(self.stats, "model_dump"):
            return self.stats.model_dump()
        return self.stats.dict()

