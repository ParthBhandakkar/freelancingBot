"""Channel segmentation: decide HOW each lead should be contacted.

The hottest leads (no website) by definition have no email to scrape —
they are reached by phone or social DM. Matching the channel to the lead
is what makes the daily queue actionable instead of a dead end.
"""

CHANNEL_EMAIL = "email"
CHANNEL_CALL = "call"
CHANNEL_DM = "dm"
CHANNEL_RESEARCH = "research"

CHANNEL_LABELS = {
    CHANNEL_EMAIL: "Email",
    CHANNEL_CALL: "Call",
    CHANNEL_DM: "DM",
    CHANNEL_RESEARCH: "Research",
}


def determine_channel(email: str = "", phone: str = "", social_links: dict | None = None, profile_url: str = "") -> str:
    if email:
        return CHANNEL_EMAIL
    if phone:
        return CHANNEL_CALL
    social = social_links or {}
    has_social = any(social.get(p) for p in ("instagram", "facebook", "linkedin", "whatsapp", "twitter"))
    if has_social or ("instagram.com" in (profile_url or "") or "facebook.com" in (profile_url or "")):
        return CHANNEL_DM
    return CHANNEL_RESEARCH


def channel_for_lead(lead, social_links: dict | None = None) -> str:
    return determine_channel(
        email=lead.email or "",
        phone=lead.phone or "",
        social_links=social_links,
        profile_url=lead.profile_url or "",
    )
