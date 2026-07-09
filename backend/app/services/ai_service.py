"""Claude-powered personalization.

Drafts outreach messages and audit-report narratives from the lead's actual
analysis data (their tech stack, their specific issues, their competitors).
Everything degrades gracefully: if ANTHROPIC_API_KEY is not set or a call
fails, callers fall back to plain templates.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

AI_MODEL = os.getenv("AI_MODEL", "claude-opus-4-8")

try:
    import anthropic
    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False


def is_ai_available() -> bool:
    return _HAS_SDK and bool(os.getenv("ANTHROPIC_API_KEY"))


def _client():
    return anthropic.AsyncAnthropic()


def _lead_context(lead, analysis=None, sender: dict | None = None) -> str:
    """Compact, factual context block about the lead for the model."""
    sender = sender or {}
    parts = [
        f"Business: {lead.business_name}",
        f"Contact name: {lead.name or 'unknown'}",
        f"City: {lead.city or 'unknown'}",
        f"Niche: {lead.niche or 'local business'}",
        f"Website: {lead.website_url or 'NONE - they have no website'}",
        f"Phone: {lead.phone or 'unknown'}",
        f"Google rating: {lead.rating or 'n/a'} ({lead.total_ratings or 0} reviews)",
        f"Online presence score: {lead.online_presence_score or 0}/100",
    ]
    if lead.flaws:
        parts.append(f"Specific issues found on their site:\n{lead.flaws}")
    if analysis is not None:
        tech = analysis.tech_stack or {}
        if any(tech.get(k) for k in ("cms", "frameworks", "ecommerce")):
            parts.append(f"Tech stack detected: {json.dumps({k: v for k, v in tech.items() if v})}")
        social = analysis.social_links or {}
        if social:
            parts.append(f"Social profiles found: {', '.join(social.keys())}")
        comp = (analysis.competitor_insights or {}).get("competitors") or []
        if comp:
            comp_lines = [f"- {c.get('name')} (rating {c.get('rating', '?')}, {c.get('total_ratings', 0)} reviews)" for c in comp[:4]]
            parts.append("Local competitors:\n" + "\n".join(comp_lines))
    parts.append(
        f"Sender: {sender.get('my_name', 'a freelance web developer')}"
        + (f" from {sender['my_company']}" if sender.get("my_company") else "")
        + f". Services: {sender.get('services_offered', 'web design and online presence for local businesses')}."
    )
    if sender.get("my_website"):
        parts.append(f"Sender's portfolio: {sender['my_website']}")
    if sender.get("calendly_link"):
        parts.append(f"Sender's booking link: {sender['calendly_link']}")
    return "\n".join(parts)


EMAIL_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["subject", "body"],
    "additionalProperties": False,
}


async def draft_outreach(lead, analysis=None, sender: dict | None = None, channel: str = "email") -> dict | None:
    """Draft a personalized outreach message. Returns {subject, body} or None on failure."""
    if not is_ai_available():
        return None

    channel_guidance = {
        "email": "Write a cold email. 90-130 words max. Subject line under 8 words, lowercase-casual, no clickbait.",
        "dm": "Write a short Instagram/Facebook DM. 40-70 words, casual, no subject needed (put a 2-3 word label in subject).",
        "call": "Write a 30-second cold-call opening script. Conversational, with a natural pause point for their response. Put 'Call script' in subject.",
    }.get(channel, "Write a cold email. 90-130 words max.")

    system = (
        "You write outreach messages for a freelance web developer contacting local businesses. "
        "Rules: reference 1-2 SPECIFIC facts about their business from the context (an issue on their site, "
        "their review count, a competitor comparison) so it obviously isn't a mass email. "
        "Plain conversational language a busy shop owner reads in 15 seconds. No buzzwords, no 'I hope this finds you well', "
        "no exclamation marks, no em-dashes. One clear low-friction ask (a quick call or reply). "
        "Sign off with the sender's real name only. Never invent facts not in the context."
    )

    try:
        client = _client()
        response = await client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            system=system,
            output_config={"format": {"type": "json_schema", "schema": EMAIL_SCHEMA}},
            messages=[{
                "role": "user",
                "content": f"{channel_guidance}\n\nContext about the lead:\n{_lead_context(lead, analysis, sender)}",
            }],
        )
        if response.stop_reason == "refusal":
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        data = json.loads(text)
        if data.get("subject") and data.get("body"):
            return {"subject": data["subject"], "body": data["body"], "ai": True}
    except Exception as e:
        logger.warning("AI draft failed: %s", e)
    return None


AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "impact": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["title", "impact", "fix"],
                "additionalProperties": False,
            },
        },
        "competitor_note": {"type": "string"},
        "recommendation": {"type": "string"},
    },
    "required": ["headline", "summary", "issues", "competitor_note", "recommendation"],
    "additionalProperties": False,
}


async def generate_audit_narrative(lead, analysis=None, sender: dict | None = None) -> dict | None:
    """Generate the written sections of an audit report. Returns dict or None on failure."""
    if not is_ai_available():
        return None

    system = (
        "You write short website/online-presence audit reports for small local businesses, "
        "on behalf of a freelance web developer. Audience: the business owner (non-technical). "
        "Tone: helpful expert, specific, zero fluff, zero scare tactics. Every issue must include "
        "the business impact in plain terms (lost customers, invisible on Google, looks untrustworthy on phones) "
        "and a concrete fix. Never invent facts not in the context. If they have NO website, the report is about "
        "what having one would change for them, grounded in their reviews/competitors."
    )

    try:
        client = _client()
        response = await client.messages.create(
            model=AI_MODEL,
            max_tokens=2048,
            system=system,
            output_config={"format": {"type": "json_schema", "schema": AUDIT_SCHEMA}},
            messages=[{
                "role": "user",
                "content": (
                    "Write the audit narrative sections (headline, 2-3 sentence summary, 3-5 issues with impact+fix, "
                    "a one-paragraph competitor note, and a closing recommendation paragraph that naturally mentions "
                    "the sender can fix these).\n\nContext:\n" + _lead_context(lead, analysis, sender)
                ),
            }],
        )
        if response.stop_reason == "refusal":
            return None
        text = next((b.text for b in response.content if b.type == "text"), "")
        return json.loads(text)
    except Exception as e:
        logger.warning("AI audit narrative failed: %s", e)
    return None
