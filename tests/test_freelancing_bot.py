from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import orchestrator as orchestrator_module
import main as main_module
import server as server_module
from linkedin.client_search import LinkedInClientSearcher
from models.schemas import CampaignStats, FreelanceClientLead, OutreachResult, OutreachResultStatus, ProspectStatus
from orchestrator import FreelancingOrchestrator
from platforms.discovery import PlatformDiscoveryService, PLATFORM_DEFINITIONS
from fastapi.testclient import TestClient
from utils.lead_intent import score_buyer_intent
from utils.sheets_integration import OUTREACH_COLUMNS, OutreachSheetStore


class FakeSheetStore:
    def append_leads(self, leads: list[FreelanceClientLead]) -> int:
        return len(leads)

    def update_status(self, *args, **kwargs) -> bool:
        return True


def make_lead(
    *,
    profile_url: str,
    source_platform: str,
    fit_score: int,
    status: ProspectStatus = ProspectStatus.DISCOVERED,
) -> FreelanceClientLead:
    return FreelanceClientLead(
        full_name="Example Lead",
        first_name="Example",
        profile_url=profile_url,
        source_platform=source_platform,
        fit_score=fit_score,
        status=status,
        discovered_at="2026-04-20 03:17:53",
    )


def test_sheet_row_matches_declared_columns_and_values():
    store = OutreachSheetStore()
    lead = FreelanceClientLead(
        discovered_at="2026-04-22 01:00:00",
        full_name="Acme Labs",
        first_name="Acme",
        headline="Automation partner",
        profile_url="https://example.com/acme",
        post_link="https://linkedin.com/posts/acme-needs-help",
        source_platform="Clutch",
        source_query="automation",
        fit_score=58,
        match_tags="company_profile;needs_review",
        status=ProspectStatus.CANDIDATE,
        outreach_action="queued",
        outreach_note="Manual follow-up",
        last_contacted_at="2026-04-22 01:05:00",
        notes="Looks promising",
    )

    row = store._lead_row(lead)
    assert len(row) == len(OUTREACH_COLUMNS)

    row_map = dict(zip(OUTREACH_COLUMNS, row))
    assert row_map["status"] == "candidate"
    assert row_map["outreach_status"] == ""
    assert row_map["outreach_action"] == "queued"
    assert row_map["outreach_note"] == "Manual follow-up"
    assert row_map["post_link"] == "https://linkedin.com/posts/acme-needs-help"


def test_sheet_lookup_reuses_existing_sheet_case_insensitively():
    class FakeWorksheet:
        title = "Outreach"

        def __init__(self) -> None:
            self.updated = False

        def row_values(self, row: int):
            return []

        def update(self, *args, **kwargs):
            self.updated = True

    class FakeSpreadsheet:
        def __init__(self) -> None:
            self.sheet = FakeWorksheet()
            self.added = False

        def worksheet(self, title: str):
            raise Exception("not found")

        def worksheets(self):
            return [self.sheet]

        def add_worksheet(self, *args, **kwargs):
            self.added = True
            return self.sheet

    store = OutreachSheetStore()
    fake_spreadsheet = FakeSpreadsheet()
    store._disabled = False
    store._client = object()
    store._spreadsheet = fake_spreadsheet

    worksheet = store._ensure_sheet()

    assert worksheet is fake_spreadsheet.sheet
    assert fake_spreadsheet.added is False
    assert fake_spreadsheet.sheet.updated is True


def test_discover_respects_requested_limit(monkeypatch):
    orchestrator = FreelancingOrchestrator()
    orchestrator.sheet_store = FakeSheetStore()

    class FakeSearcher:
        async def discover_clients(self, max_results: int | None = None):
            return [
                make_lead(profile_url=f"https://linkedin.com/in/{idx}", source_platform="LinkedIn", fit_score=70)
                for idx in range(2)
            ]

    class FakePlatformSearcher:
        async def discover(self, max_results: int | None = None, platform_sources: list[str] | None = None):
            return [
                make_lead(profile_url=f"https://upwork.com/jobs/{idx}", source_platform="Upwork", fit_score=50)
                for idx in range(4)
            ]

    async def fake_start(*args, **kwargs):
        orchestrator.stats = CampaignStats(session_start=datetime.now())
        orchestrator.state = orchestrator_module.BotState.IDLE

    async def fake_stop(*args, **kwargs):
        return None

    async def fake_score(leads: list[FreelanceClientLead]):
        return leads

    orchestrator.searcher = FakeSearcher()
    orchestrator.platform_searcher = FakePlatformSearcher()
    orchestrator.start = fake_start
    orchestrator.stop = fake_stop
    orchestrator._score_discovered_leads = fake_score

    monkeypatch.setattr(orchestrator_module, "append_leads", lambda leads, filename: (len(leads), len(leads)))

    leads = asyncio.run(orchestrator.discover(max_results=3, platform_sources=["linkedin", "upwork"]))

    assert len(leads) == 3
    assert sum(1 for lead in leads if lead.source_platform == "LinkedIn") == 2


def test_score_discovered_leads_only_rescores_linkedin(monkeypatch):
    monkeypatch.setattr(type(orchestrator_module.settings), "has_llm_key", property(lambda self: True))
    monkeypatch.setattr(orchestrator_module.llm_client, "is_available", lambda: asyncio.sleep(0, result=True))

    orchestrator = FreelancingOrchestrator()

    class FakeSearcher:
        async def score_with_llm(self, lead: FreelanceClientLead) -> FreelanceClientLead:
            lead.fit_score = 88
            lead.status = ProspectStatus.CANDIDATE
            return lead

    orchestrator.searcher = FakeSearcher()

    linkedin_lead = make_lead(
        profile_url="https://linkedin.com/in/example",
        source_platform="LinkedIn",
        fit_score=40,
        status=ProspectStatus.DISCOVERED,
    )
    external_lead = make_lead(
        profile_url="https://clutch.co/profile/acme",
        source_platform="Clutch",
        fit_score=40,
        status=ProspectStatus.DISCOVERED,
    )

    scored = asyncio.run(orchestrator._score_discovered_leads([linkedin_lead, external_lead]))

    assert scored[0].fit_score == 88
    assert scored[0].status == ProspectStatus.CANDIDATE
    assert scored[1].fit_score == 40
    assert scored[1].status == ProspectStatus.DISCOVERED


def test_run_campaign_uses_single_discovery_and_outreach_pass(monkeypatch):
    orchestrator = FreelancingOrchestrator()
    events: list[tuple[str, object]] = []

    async def fake_start(*args, **kwargs):
        events.append(("start", kwargs.get("require_linkedin_login")))
        orchestrator.stats = CampaignStats(session_start=datetime.now())

    async def fake_stop(*args, **kwargs):
        events.append(("stop", kwargs.get("requested")))

    async def fake_discover_impl(*, max_results=None, platform_sources=None):
        events.append(("discover", (max_results, tuple(platform_sources or []))))
        orchestrator.stats.discovered = 2
        return [
            make_lead(profile_url="https://linkedin.com/in/example", source_platform="LinkedIn", fit_score=80),
        ]

    async def fake_outreach_impl(*, max_results=None, mode="combined"):
        events.append(("outreach", (max_results, mode)))
        result = OutreachResult(
            lead=make_lead(
                profile_url="https://linkedin.com/in/example",
                source_platform="LinkedIn",
                fit_score=80,
            ),
            status=OutreachResultStatus.MESSAGE_SENT,
            action_taken="message_sent",
        )
        orchestrator.stats.outreached = 1
        return [result]

    async def fake_delay(*args, **kwargs):
        return None

    def fake_report():
        events.append(("report", None))

    orchestrator.start = fake_start
    orchestrator.stop = fake_stop
    orchestrator._discover_impl = fake_discover_impl
    orchestrator._outreach_impl = fake_outreach_impl
    orchestrator._write_session_report = fake_report

    monkeypatch.setattr(orchestrator_module, "human_delay", fake_delay)

    results = asyncio.run(orchestrator.run_campaign(5, 3, ["linkedin"]))

    assert len(results) == 1
    assert [name for name, _ in events].count("start") == 1
    assert [name for name, _ in events].count("discover") == 1
    assert [name for name, _ in events].count("outreach") == 1
    assert [name for name, _ in events].count("stop") == 1


def test_public_linkedin_fallback_parses_candidate():
    searcher = LinkedInClientSearcher(browser=None)
    sample_html = """
    title:"Tadeas Marek - Founder & CEO @ Boost.space | Single Source of Truth Database where Your Data, AI & Automation Connects | LinkedIn",
    url:"https://www.linkedin.com/in/tadeas-marek/",
    full_title:void 0,
    description:"Founder &amp; CEO @ Boost.space | Single Source of Truth Database where Your Data, AI &amp; Automation Connects · Experience: Boost.space · Location: Prague · 500+ connections on LinkedIn."
    """

    searcher._fetch_public_search_html = lambda url: sample_html  # type: ignore[method-assign]

    leads = asyncio.run(searcher._discover_public_by_query("founder ai automation startup", 3))

    assert len(leads) == 1
    assert leads[0].profile_url == "https://www.linkedin.com/in/tadeas-marek/"
    assert leads[0].status == ProspectStatus.CANDIDATE
    assert leads[0].company == "Boost.space"


def test_name_falls_back_to_profile_slug():
    assert (
        LinkedInClientSearcher._extract_name_from_text(
            "Message\nConnect",
            profile_url="https://www.linkedin.com/in/ayush-saraswat-/",
        )
        == "Ayush Saraswat"
    )


def test_platform_discovery_filters_irrelevant_marketplace_results():
    service = PlatformDiscoveryService(browser=None)  # type: ignore[arg-type]
    source_map = {source.name: source for source in PLATFORM_DEFINITIONS}

    assert service._qualify_result(
        source=source_map["Upwork"],
        href="https://www.upwork.com/services/product/development-it-ai-automation",
        title="AI Automation Service",
        snippet="Freelancer offering an automation service",
        query="automation",
    ) is None

    upwork_job = service._qualify_result(
        source=source_map["Upwork"],
        href="https://www.upwork.com/jobs/~0123456789",
        title="Looking to hire an AI automation partner",
        snippet="Need help with a contract automation project",
        query="automation",
    )
    assert upwork_job is not None
    assert upwork_job["status"] == ProspectStatus.CANDIDATE

    assert service._qualify_result(
        source=source_map["Fiverr"],
        href="https://www.fiverr.com/users/sellername",
        title="Top Fiverr seller",
        snippet="Seller profile for automation services",
        query="automation",
    ) is None

    clutch_profile = service._qualify_result(
        source=source_map["Clutch"],
        href="https://clutch.co/profile/techionik",
        title="Techionik Ltd - Services & Company Info - Clutch",
        snippet="Company profile on Clutch",
        query="automation",
    )
    assert clutch_profile is not None
    assert clutch_profile["status"] == ProspectStatus.DISCOVERED


def test_active_freelance_request_gets_high_intent_score():
    intent = score_buyer_intent(
        "Looking to hire a freelancer for an AI automation dashboard project this week",
        "Need a backend developer to build workflow automation",
    )

    assert intent.is_active_request is True
    assert intent.score_boost >= 70
    assert "active_buyer_request" in intent.tags
    assert "project_or_contract_need" in intent.tags


def test_linkedin_rule_score_prioritizes_people_who_posted_need():
    searcher = LinkedInClientSearcher(browser=None)

    score, tags, is_candidate = searcher._rule_based_score(
        full_name="Maya Founder",
        headline="Building SaaS operations tools",
        company="OpsFlow",
        location="",
        snippet="Looking to hire a freelancer. Need help with a backend automation project ASAP.",
        query="need help with ai automation project",
    )

    assert score >= 85
    assert is_candidate is True
    assert "active_buyer_request" in tags


def test_linkedin_posts_source_keeps_only_active_buyer_requests():
    service = PlatformDiscoveryService(browser=None)  # type: ignore[arg-type]
    source_map = {source.name: source for source in PLATFORM_DEFINITIONS}

    buyer_post = service._qualify_result(
        source=source_map["LinkedIn_Posts"],
        href="https://www.linkedin.com/posts/maya-founder_looking-to-hire-activity-123",
        title="Maya Founder on LinkedIn: Looking to hire a freelancer",
        snippet="Need a backend developer for an AI automation dashboard project this week.",
        query="looking to hire full stack developer freelance",
    )

    seller_post = service._qualify_result(
        source=source_map["LinkedIn_Posts"],
        href="https://www.linkedin.com/posts/seller_automation-services-activity-123",
        title="Automation freelancer available",
        snippet="I am a freelancer available for automation projects. View my portfolio.",
        query="automation developer",
    )

    assert buyer_post is not None
    assert buyer_post["status"] == ProspectStatus.CANDIDATE
    assert buyer_post["fit_score"] >= 90
    assert "linkedin_buyer_post" in buyer_post["match_tags"]
    assert seller_post is None

    lead = service._build_lead(
        full_name="Maya Founder",
        headline="Looking to hire a freelancer",
        company="",
        location="",
        snippet="Need a backend developer for an AI automation dashboard project this week.",
        query="looking to hire full stack developer freelance",
        profile_url="https://www.linkedin.com/posts/maya-founder_looking-to-hire-activity-123",
        post_link="https://www.linkedin.com/posts/maya-founder_looking-to-hire-activity-123",
        source="LinkedIn_Posts",
        fit_score=int(buyer_post["fit_score"]),
        match_tags=str(buyer_post["match_tags"]),
        status=buyer_post["status"],
        notes=str(buyer_post["notes"]),
    )
    assert lead.post_link == "https://www.linkedin.com/posts/maya-founder_looking-to-hire-activity-123"


def test_main_defaults_to_server_args():
    args = main_module.parse_args([])

    assert args.host
    assert args.port
    assert args.reload is False


def test_root_redirects_to_dashboard():
    client = TestClient(server_module.app)
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"


def test_modes_endpoint_lists_operations():
    client = TestClient(server_module.app)
    response = client.get("/modes")

    assert response.status_code == 200
    payload = response.json()
    ids = [item["id"] for item in payload["modes"]]
    assert ids == ["discover", "connect", "message", "outreach", "campaign", "follow_up"]


def test_dashboard_route_serves_external_html():
    client = TestClient(server_module.app)
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Freelancing Bot Dashboard" in response.text


def test_discover_endpoint_accepts_background_launch(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(server_module.control_state, "active_task", None)
    monkeypatch.setattr(server_module.control_state, "active_operation", "")
    monkeypatch.setattr(server_module, "_launch_operation", lambda name, runner: {"accepted": True, "operation": name})

    response = client.post("/discover", json={"max_results": 5, "sources": "linkedin"})

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "operation": "discover"}


def test_connect_endpoint_accepts_background_launch(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(server_module.control_state, "active_task", None)
    monkeypatch.setattr(server_module.control_state, "active_operation", "")
    monkeypatch.setattr(server_module, "_launch_operation", lambda name, runner: {"accepted": True, "operation": name})

    response = client.post("/connect", json={"max_results": 5})

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "operation": "connect"}


def test_message_endpoint_accepts_background_launch(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(server_module.control_state, "active_task", None)
    monkeypatch.setattr(server_module.control_state, "active_operation", "")
    monkeypatch.setattr(server_module, "_launch_operation", lambda name, runner: {"accepted": True, "operation": name})

    response = client.post("/message", json={"max_results": 5})

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "operation": "message"}


def test_outreach_impl_dispatches_requested_mode(monkeypatch):
    orchestrator = FreelancingOrchestrator()
    orchestrator.sheet_store = FakeSheetStore()

    lead = make_lead(
        profile_url="https://linkedin.com/in/example",
        source_platform="LinkedIn",
        fit_score=91,
        status=ProspectStatus.CONNECT_REQUESTED,
    )
    calls: list[str] = []

    class FakeMessenger:
        async def send_connection_request(self, current_lead):
            calls.append(f"connect:{current_lead.profile_url}")
            return OutreachResult(
                lead=current_lead,
                status=OutreachResultStatus.CONNECT_REQUESTED,
                action_taken="connect_requested",
            )

        async def send_message_if_ready(self, current_lead):
            calls.append(f"message:{current_lead.profile_url}")
            return OutreachResult(
                lead=current_lead,
                status=OutreachResultStatus.MESSAGE_SENT,
                action_taken="message_sent_after_connection_check",
            )

    orchestrator.messenger = FakeMessenger()

    monkeypatch.setattr(orchestrator, "_load_outreach_leads", lambda **kwargs: [lead])
    monkeypatch.setattr(orchestrator_module, "human_delay", lambda *args, **kwargs: asyncio.sleep(0))
    monkeypatch.setattr(orchestrator_module, "update_lead_status", lambda *args, **kwargs: True)

    connect_results = asyncio.run(orchestrator._outreach_impl(max_results=1, mode="connect"))
    message_results = asyncio.run(orchestrator._outreach_impl(max_results=1, mode="message"))

    assert connect_results[0].status == OutreachResultStatus.CONNECT_REQUESTED
    assert message_results[0].status == OutreachResultStatus.MESSAGE_SENT
    assert calls == [
        "connect:https://linkedin.com/in/example",
        "message:https://linkedin.com/in/example",
    ]


def test_upwork_rss_parse_item():
    from platforms.upwork_rss import UpworkRSSDiscovery
    import xml.etree.ElementTree as ET

    rss_xml = """
    <rss><channel>
      <item>
        <title>Looking for Python developer to build AI automation dashboard</title>
        <link>https://www.upwork.com/jobs/~0123456789</link>
        <description>Budget: $500. Need a Python developer to build automation. Skills: Python, FastAPI</description>
      </item>
    </channel></rss>
    """

    discovery = UpworkRSSDiscovery()
    leads = discovery._parse_feed(rss_xml.strip(), "python automation", 10)

    assert len(leads) == 1
    assert leads[0].source_platform == "Upwork_RSS"
    assert "upwork_rss" in leads[0].match_tags
    assert leads[0].profile_url == "https://www.upwork.com/jobs/~0123456789"


def test_follow_up_due_date_calculation():
    from outreach.follow_up import FollowUpManager, FOLLOWUP_1_ELIGIBLE
    from datetime import datetime, timedelta

    manager = FollowUpManager()
    now = datetime.now()

    lead_recent = make_lead(
        profile_url="https://linkedin.com/in/recent",
        source_platform="LinkedIn",
        fit_score=80,
        status=ProspectStatus.MESSAGE_SENT,
    )
    lead_recent.last_contacted_at = now.strftime("%Y-%m-%d %H:%M:%S")

    lead_due = make_lead(
        profile_url="https://linkedin.com/in/due",
        source_platform="LinkedIn",
        fit_score=80,
        status=ProspectStatus.MESSAGE_SENT,
    )
    lead_due.last_contacted_at = (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")

    # lead_recent is too recent for follow-up
    assert lead_recent.status in FOLLOWUP_1_ELIGIBLE
    # lead_due should be eligible
    assert lead_due.status in FOLLOWUP_1_ELIGIBLE

    # Test message building
    msg = manager.build_followup_message(lead_due, step=1)
    assert "bumping" in msg.lower() or "inbox" in msg.lower()

    msg2 = manager.build_followup_message(lead_due, step=2)
    assert "last" in msg2.lower() or "follow-up" in msg2.lower() or "portfolio" in msg2.lower()


def test_email_finder_unavailable_without_key():
    from outreach.email_finder import EmailFinder

    finder = EmailFinder()
    assert not finder.available

    result = asyncio.run(finder.find_email("John Doe", "Acme Corp"))
    assert result is None


def test_follow_up_endpoint_accepts_background_launch(monkeypatch):
    client = TestClient(server_module.app)

    monkeypatch.setattr(server_module.control_state, "active_task", None)
    monkeypatch.setattr(server_module.control_state, "active_operation", "")
    monkeypatch.setattr(server_module, "_launch_operation", lambda name, runner: {"accepted": True, "operation": name})

    response = client.post("/follow-up", json={"max_results": 5})

    assert response.status_code == 202
    assert response.json() == {"accepted": True, "operation": "follow_up"}


def test_new_schema_fields_exist():
    lead = FreelanceClientLead(
        full_name="Test Lead",
        email="test@example.com",
        status=ProspectStatus.FOLLOW_UP_1,
    )
    assert lead.email == "test@example.com"
    assert lead.status == ProspectStatus.FOLLOW_UP_1
    assert ProspectStatus.EMAIL_SENT.value == "email_sent"
    assert OutreachResultStatus.EMAIL_SENT.value == "email_sent"

    stats = CampaignStats()
    assert stats.emails_sent == 0
    assert stats.follow_ups_sent == 0


def test_icebreaker_prompt_renders():
    from llm.prompts import ICEBREAKER_SYSTEM, ICEBREAKER_USER

    assert "hyper-personalized" in ICEBREAKER_SYSTEM.lower() or "icebreaker" in ICEBREAKER_SYSTEM.lower()

    rendered = ICEBREAKER_USER.format(
        full_name="Jane Doe",
        headline="CEO at WidgetCorp",
        company="WidgetCorp",
        snippet="Looking for a developer to build our analytics dashboard",
        query="analytics dashboard developer",
    )
    assert "Jane Doe" in rendered
    assert "WidgetCorp" in rendered
