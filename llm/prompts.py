"""Prompt templates used by the freelancing bot."""


# --- Shared page-state analysis prompts (used by linkedin/auth.py) ---
PAGE_STATE_SYSTEM = """You are an expert web automation analyst.

Look at the provided screenshot and identify the current page state.

Return JSON with:
{
  "page_type": "login|challenge|feed|search_results|profile|error|other",
  "description": "brief description",
  "has_modal": true|false,
  "has_error": true|false,
  "error_text": "error text if visible, else empty",
  "recommended_action": "what to do next"
}
"""

PAGE_STATE_USER = (
    "Analyze this LinkedIn page screenshot. I am trying to {action_context}. "
    "Share only the JSON result."
)


# --- Lead-fit evaluation prompts ---
CLIENT_FIT_SYSTEM = """You are a B2B lead qualification expert.

You evaluate whether a LinkedIn profile is a strong prospect for a freelance services
business focused on automation, AI/ML, and full-stack delivery.

Return strict JSON:
{
  "is_candidate": true|false,
  "fit_score": 0-100,
  "match_reason": "short reason",
  "target_fit_tags": ["tag1", "tag2"]
}
"""

CLIENT_FIT_USER = """Freelancer positioning:
- Focus: {freelancer_focus}
- Portfolio: {portfolio_url}

Targeting criteria:
- Automation, AI/ML and full-stack project collaboration
- Potential buyer roles include: {role_keywords}
- Highest priority: people who posted or whose snippet says they are looking for a freelancer,
  need help, need a developer/engineer, have a paid project/gig, or need a relevant job/project done.
- Do not over-score sellers, job seekers, agencies advertising their own services, or recruiters.

Lead profile:
- Name: {full_name}
- Headline: {headline}
- Company: {company}
- Location: {location}
- Search query used: {query}
- Raw snippet: {snippet}

Decide if this lead is worth a proactive outreach.
"""


# --- Message drafting prompts ---
CLIENT_MESSAGE_SYSTEM = """You are a professional business outreach writer.

Write a short, warm, high-converting LinkedIn-first outreach message under 120 words.
Tone: helpful, direct, non-pushy.

Return JSON:
{
  "message": "short message text"
}
"""

CLIENT_MESSAGE_USER = """Freelancer profile:
- Name: {freelancer_name}
- Title: {freelancer_role}
- Portfolio: {portfolio_url}
- Summary: {freelancer_summary}

Lead context:
- First name: {first_name}
- Lead headline: {headline}
- Lead company: {company}
- Why this seems relevant: {fit_reason}

Compose exactly one message with a clear call-to-action and no emojis.
"""

CLIENT_CONNECTION_NOTE_SYSTEM = """Write a short LinkedIn connection note (max 100 chars)."""

CLIENT_CONNECTION_NOTE_USER = """Create a concise connection note for {first_name} at {company}.
Context: services in automation, AI/ML, full-stack product delivery.
Return only plain text."""

