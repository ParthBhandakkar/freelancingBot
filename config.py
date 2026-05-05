"""Configuration management for the Freelancing Bot."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
LOG_DIR = BASE_DIR / "logs"
BROWSER_DATA_DIR = BASE_DIR / "browser_data"


for _path in (DATA_DIR, DATA_DIR / "reports", SCREENSHOT_DIR, LOG_DIR, BROWSER_DATA_DIR):
    _path.mkdir(parents=True, exist_ok=True)


def _split_csv(raw: str | None) -> list[str]:
    """Split comma/semicolon/newline-separated environment values."""
    if not raw:
        return []
    pieces = re.split(r"[,;\n]", raw)
    values: list[str] = []
    for piece in pieces:
        value = piece.strip()
        if value:
            values.append(value)
    return values


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in values:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


class Settings(BaseSettings):
    # ── LinkedIn ────────────────────────────────────────────────────────
    linkedin_email: str = ""
    linkedin_password: str = ""

    # ── LLM ────────────────────────────────────────────────────────────
    llm_provider: Literal["kimi", "ollama", "openai"] = "ollama"
    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "kimi-k2.5"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "kimi-k2.5:cloud"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    # ── Server ─────────────────────────────────────────────────────────
    server_host: str = "0.0.0.0"
    server_port: int = 8080

    # ── Browser ────────────────────────────────────────────────────────
    headless: bool = False
    slow_mo: int = 50
    browser_timeout: int = 60_000
    fast_easy_apply: bool = False

    # ── Campaign timing ───────────────────────────────────────────────
    search_delay_min: float = 3.0
    search_delay_max: float = 7.0
    outreach_delay_min: float = 2.0
    outreach_delay_max: float = 6.0

    # ── Campaign controls ─────────────────────────────────────────────
    max_discovery_results: int = 120
    max_outreach_per_run: int = 20
    min_fit_score: int = 55
    scroll_rounds_per_query: int = 7
    discover_platforms: str = "linkedin,linkedin_posts,linkedin_posts_native,upwork,upwork_rss,clutch,yc"
    max_web_results_per_query: int = 4

    # ── Profiling and targeting ───────────────────────────────────────
    portfolio_url: str = "https://portfolio-bhandakkarparth.netlify.app/"
    freelancer_name: str = "Parth Bhandakkar"
    freelancer_role: str = "Backend Developer & AI Engineer"
    freelancer_summary: str = (
        "I help teams ship backend-heavy SaaS products, analytics platforms, "
        "AI automation, and production-ready web applications."
    )
    freelancer_focus: str = "Backend Engineering, AI Automation, Analytics Dashboards, and SaaS Delivery"

    search_queries: str = (
        "founder ai automation startup, "
        "cto saas backend platform, "
        "head of product analytics dashboard, "
        "operations head workflow automation, "
        "ecommerce founder custom platform, "
        "computer vision founder ai product"
    )
    buyer_intent_search_queries: str = (
        '"looking for" freelancer backend automation, '
        '"need help with" ai automation project, '
        '"looking to hire" full stack developer freelance, '
        '"need a developer" saas dashboard, '
        '"any recommendations" automation developer, '
        '"paid project" backend developer'
    )
    linkedin_post_queries: str = (
        "looking for developer, "
        "need help with automation, "
        "hiring freelancer backend, "
        "need a developer for, "
        "looking to hire engineer, "
        "who can build"
    )
    upwork_rss_queries: str = (
        "backend developer, "
        "AI automation, "
        "full stack developer, "
        "python developer api, "
        "saas dashboard, "
        "workflow automation"
    )
    role_keywords: str = (
        "founder,co-founder,ceo,cto,vp engineering,head of engineering,"
        "head of product,engineering manager,operations head,technical founder"
    )
    industry_keywords: str = (
        "ai,artificial intelligence,machine learning,automation,"
        "backend,software,saas,tech startup,ecommerce,analytics,dashboard,"
        "computer vision,photo recognition,data platform,real estate,hospitality"
    )
    lead_blacklist_keywords: str = (
        "recruiter,hiring manager,job board,training,agency,placement,staffing,"
        "consultant,freelancer,coach,open to work,job seeker"
    )

    # ── Outreach content ──────────────────────────────────────────────
    outreach_send_message_if_possible: bool = True
    soft_pitch_enabled: bool = True
    outreach_message_template: str = (
        "Hi {first_name}, I noticed your work in {company}. "
        "I help teams build practical automation and AI/ML product features with "
        "strong full-stack execution. If you'd like, I can share a quick plan using "
        "my portfolio at {portfolio_url}."
    )
    outreach_connection_note_template: str = (
        "Hi {first_name}, fellow builder in the AI/automation space. "
        "Would love to connect!"
    )
    outreach_pitch_message_template: str = (
        "Hi {first_name}, thanks for connecting! I noticed your work at {company}. "
        "I help teams ship backend-heavy products, AI automation, and analytics dashboards. "
        "Would love to share a quick plan if you have any upcoming projects — "
        "here's my portfolio: {portfolio_url}"
    )
    outreach_signature: str = "Best, {freelancer_name}"

    # ── Follow-up nurturing ───────────────────────────────────────────
    followup_1_delay_days: int = 3
    followup_2_delay_days: int = 7
    followup_1_template: str = (
        "Hey {first_name}, just bumping this to the top of your inbox. "
        "Let me know if you have any bandwidth to chat this week about "
        "your {company} projects."
    )
    followup_2_template: str = (
        "Hi {first_name}, last follow-up from me! If you ever need help with "
        "backend engineering, AI automation, or dashboard builds, I'm a message away. "
        "Portfolio: {portfolio_url}"
    )

    # ── Email outreach ────────────────────────────────────────────────
    hunter_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = ""
    email_daily_limit: int = 30
    email_subject_template: str = (
        "Quick question about {company}"
    )
    email_body_template: str = (
        "Hi {first_name},\n\n"
        "I came across {company} and was impressed by what you're building. "
        "I specialize in backend engineering, AI automation, and analytics dashboards "
        "— the kind of work that accelerates product teams.\n\n"
        "Would you be open to a quick chat about any upcoming projects?\n\n"
        "Portfolio: {portfolio_url}\n\n"
        "Best,\n{freelancer_name}"
    )
    email_followup_1_subject: str = "Re: Quick question about {company}"
    email_followup_1_body: str = (
        "Hi {first_name},\n\n"
        "Just bumping my previous note. If you have any backend, AI, or automation "
        "projects coming up, I'd love to help.\n\n"
        "Best,\n{freelancer_name}"
    )
    email_followup_2_subject: str = "Re: Quick question about {company}"
    email_followup_2_body: str = (
        "Hi {first_name},\n\n"
        "Last follow-up from me! If you ever need help with engineering or "
        "automation, I'm one reply away. Portfolio: {portfolio_url}\n\n"
        "Cheers,\n{freelancer_name}"
    )

    # ── Persistence ───────────────────────────────────────────────────
    lead_store_file: str = "freelance_leads.csv"

    # ── Google Sheets (Outreach tracking) ───────────────────────────
    google_sheet_id: str = "15GN43sNJi_l2ExORjz60mB4qcDxXRW_kOYuDciUtV-s"
    google_credentials_file: str = "credentials.json"
    google_outreach_sheet_name: str = "outreach"
    google_outreach_enabled: bool = True

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"

    @property
    def search_query_list(self) -> list[str]:
        return _dedupe(_split_csv(self.search_queries))

    @property
    def buyer_intent_query_list(self) -> list[str]:
        return _dedupe(_split_csv(self.buyer_intent_search_queries))

    @property
    def all_search_query_list(self) -> list[str]:
        return _dedupe(self.buyer_intent_query_list + self.search_query_list)

    @property
    def linkedin_post_query_list(self) -> list[str]:
        return _dedupe(_split_csv(self.linkedin_post_queries))

    @property
    def upwork_rss_query_list(self) -> list[str]:
        return _dedupe(_split_csv(self.upwork_rss_queries))

    @property
    def has_hunter_key(self) -> bool:
        return bool(self.hunter_api_key.strip())

    @property
    def has_smtp_config(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_user.strip())

    @property
    def discover_platform_list(self) -> list[str]:
        return _dedupe([item.lower() for item in _split_csv(self.discover_platforms)])

    @property
    def role_keyword_list(self) -> list[str]:
        return _dedupe([item.lower() for item in _split_csv(self.role_keywords)])

    @property
    def industry_keyword_list(self) -> list[str]:
        return _dedupe([item.lower() for item in _split_csv(self.industry_keywords)])

    @property
    def lead_blacklist_list(self) -> list[str]:
        return _dedupe([item.lower() for item in _split_csv(self.lead_blacklist_keywords)])

    @property
    def outreach_message(self) -> str:
        return (self.outreach_message_template or "").strip()

    @property
    def connection_note(self) -> str:
        return (self.outreach_connection_note_template or "").strip()

    @property
    def outreach_signature_text(self) -> str:
        return (self.outreach_signature or "").format(
            freelancer_name=self.freelancer_name,
            freelancer_role=self.freelancer_role,
            portfolio_url=self.portfolio_url,
        )

    @property
    def has_llm_key(self) -> bool:
        if self.llm_provider == "kimi":
            return bool(self.kimi_api_key.strip())
        if self.llm_provider == "openai":
            return bool(self.openai_api_key.strip())
        if self.llm_provider == "ollama":
            return bool(self.ollama_base_url.strip())
        return False


settings = Settings()

