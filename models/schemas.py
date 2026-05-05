"""Pydantic models for freelancing prospect automation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProspectStatus(str, Enum):
    DISCOVERED = "discovered"
    CANDIDATE = "candidate"
    MESSAGE_SENT = "message_sent"
    CONNECT_REQUESTED = "connect_requested"
    CONNECTED = "connected"
    FOLLOW_UP_1 = "follow_up_1"
    FOLLOW_UP_2 = "follow_up_2"
    FOLLOW_UP_DONE = "follow_up_done"
    EMAIL_SENT = "email_sent"
    EMAIL_FOLLOW_UP_1 = "email_follow_up_1"
    EMAIL_FOLLOW_UP_2 = "email_follow_up_2"
    SKIPPED = "skipped"
    FAILED = "failed"


class OutreachResultStatus(str, Enum):
    MESSAGE_SENT = "message_sent"
    CONNECT_REQUESTED = "connect_requested"
    CONNECTED = "connected"
    EMAIL_SENT = "email_sent"
    SKIPPED = "skipped"
    FAILED = "failed"
    BLOCKED = "blocked"


class BotState(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    DISCOVERING = "discovering"
    OUTREACHING = "outreaching"
    FOLLOWING_UP = "following_up"
    STOPPED = "stopped"
    PAUSED = "paused"
    ERROR = "error"


class FreelanceClientLead(BaseModel):
    lead_id: str = ""
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    headline: str = ""
    company: str = ""
    location: str = ""
    email: str = ""
    profile_url: str = ""
    post_link: str = ""
    profile_snippet: str = ""
    matched_query: str = ""
    source_platform: str = "LinkedIn"
    source_query: str = ""
    fit_score: int = 0
    match_tags: str = ""
    status: ProspectStatus = ProspectStatus.DISCOVERED
    outreach_action: str = ""
    outreach_note: str = ""
    last_contacted_at: str = ""
    discovered_at: str = ""
    notes: str = ""


class OutreachResult(BaseModel):
    lead: FreelanceClientLead
    status: OutreachResultStatus
    action_taken: str = ""
    message_text: str = ""
    connected_status: str = ""
    notes: str = ""
    errors: list[str] = Field(default_factory=list)
    sent_at: Optional[datetime] = None


class CampaignStats(BaseModel):
    discovered: int = 0
    candidate: int = 0
    outreached: int = 0
    messages_sent: int = 0
    connect_requested: int = 0
    connected: int = 0
    emails_sent: int = 0
    follow_ups_sent: int = 0
    failed: int = 0
    skipped: int = 0
    session_start: Optional[datetime] = None
    session_end: Optional[datetime] = None
    results: list[OutreachResult] = Field(default_factory=list)

