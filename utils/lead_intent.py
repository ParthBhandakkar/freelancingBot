"""Buyer-intent scoring helpers for freelance lead discovery."""
from __future__ import annotations

import re
from dataclasses import dataclass

from config import settings
from utils.helpers import clean_text


DIRECT_REQUEST_PATTERNS = (
    r"\blooking\s+(?:for|to\s+hire)\b",
    r"\bneed(?:ing|ed|s)?\s+(?:a|an|some|someone|help|freelancer|developer|engineer|agency|team)\b",
    r"\bhiring\s+(?:a|an|for|freelancer|developer|engineer|contractor|agency)\b",
    r"\bseeking\s+(?:a|an|freelancer|developer|engineer|contractor|agency|help)\b",
    r"\bcan\s+anyone\s+(?:build|help|recommend|refer)\b",
    r"\bany\s+recommendations?\s+for\b",
    r"\bwho\s+can\s+(?:build|create|develop|fix|automate|integrate)\b",
    r"\bpaid\s+(?:gig|project|work|contract)\b",
)

PROJECT_PATTERNS = (
    r"\bproject\b",
    r"\bcontract\b",
    r"\bfreelance(?:r)?\b",
    r"\bconsultant\b",
    r"\bpart[-\s]?time\b",
    r"\bshort[-\s]?term\b",
    r"\bbuild\s+(?:an?|my|our)\b",
    r"\bhelp\s+(?:with|us|me)\b",
)

URGENCY_PATTERNS = (
    r"\basap\b",
    r"\burgent(?:ly)?\b",
    r"\bthis\s+week\b",
    r"\bimmediate(?:ly)?\b",
    r"\btoday\b",
    r"\bnow\b",
)

SELLER_CONTEXT_PATTERNS = (
    r"\bi\s+(?:am|'m)\s+(?:a\s+)?freelancer\b",
    r"\bavailable\s+for\s+(?:freelance|contract|projects?)\b",
    r"\bopen\s+to\s+(?:work|freelance|contract)\b",
    r"\bportfolio\b",
    r"\bmy\s+services\b",
)


@dataclass(frozen=True)
class BuyerIntentScore:
    score_boost: int
    tags: list[str]
    is_active_request: bool
    has_profession_match: bool
    reason: str


def score_buyer_intent(*parts: str) -> BuyerIntentScore:
    """Score whether text shows someone actively needs freelance/project help."""
    text = clean_text(" ".join(part for part in parts if part)).lower()
    if not text:
        return BuyerIntentScore(0, [], False, False, "")

    direct_hits = _pattern_hits(text, DIRECT_REQUEST_PATTERNS)
    project_hits = _pattern_hits(text, PROJECT_PATTERNS)
    urgency_hits = _pattern_hits(text, URGENCY_PATTERNS)
    seller_hits = _pattern_hits(text, SELLER_CONTEXT_PATTERNS)

    profession_terms = [
        term
        for term in settings.industry_keyword_list + _profession_keywords()
        if term and term in text
    ]

    score = 0
    tags: list[str] = []

    if direct_hits:
        score += 45
        tags.append("active_buyer_request")
    if project_hits:
        score += min(20, len(project_hits) * 8)
        tags.append("project_or_contract_need")
    if profession_terms:
        score += min(25, len(profession_terms) * 7)
        tags.extend(profession_terms[:4])
    if urgency_hits:
        score += 10
        tags.append("urgent_need")
    if seller_hits:
        score -= 35
        tags.append("seller_context")

    is_active_request = bool(direct_hits and (profession_terms or project_hits) and score >= 40)
    reason = ""
    if is_active_request:
        reason = "Text shows an active request for freelance/project help in the target service area."
    elif direct_hits:
        reason = "Text shows buyer intent, but the target service match is weaker."

    return BuyerIntentScore(
        score_boost=max(-35, min(80, score)),
        tags=list(dict.fromkeys(tags)),
        is_active_request=is_active_request,
        has_profession_match=bool(profession_terms),
        reason=reason,
    )


def _pattern_hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _profession_keywords() -> list[str]:
    return [
        "backend developer",
        "backend engineer",
        "full stack",
        "full-stack",
        "software developer",
        "software engineer",
        "ai engineer",
        "automation expert",
        "automation developer",
        "dashboard",
        "analytics dashboard",
        "saas",
        "web app",
        "api integration",
        "workflow automation",
    ]
