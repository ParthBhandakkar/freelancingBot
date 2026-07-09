"""Generates a polished, self-contained HTML audit report for a lead.

Saved under backend/generated_assets/ and served at /assets/. The report is
print-to-PDF ready (the browser's Print dialog produces a clean one-pager).
Narrative sections come from Claude when available, otherwise from a
data-driven template fallback.
"""

import os
import html
import logging
from datetime import date

logger = logging.getLogger(__name__)

ASSETS_DIR = os.path.join(os.getcwd(), "generated_assets")


def _fallback_narrative(lead, analysis=None) -> dict:
    issues = []
    for line in (lead.flaws or "").split("\n"):
        line = line.strip().lstrip("-• ")
        if line:
            issues.append({
                "title": line,
                "impact": "Issues like this make the site harder to find and less convincing for potential customers.",
                "fix": "This is a quick, standard fix for a web professional.",
            })
    if not issues and not lead.website_url:
        issues = [
            {
                "title": "No website found",
                "impact": f"Customers searching for a {lead.niche or 'business'} in {lead.city or 'your area'} can't find you online, and competitors with websites take those customers.",
                "fix": "A simple, fast one-page website with your services, photos, hours and a contact button.",
            },
            {
                "title": "Relying only on your Google listing",
                "impact": "A Google listing alone can't show your work, answer common questions, or take bookings.",
                "fix": "Link a website to the listing so searchers land somewhere that sells for you 24/7.",
            },
        ]
    if not issues:
        issues = [{
            "title": "General online presence review",
            "impact": "Small gaps in speed, mobile experience and search visibility add up to lost customers.",
            "fix": "A focused round of improvements addressing the highest-impact items first.",
        }]

    comp = ((analysis.competitor_insights or {}) if analysis is not None else {}).get("competitors") or []
    if comp:
        names = ", ".join(c.get("name", "") for c in comp[:3] if c.get("name"))
        competitor_note = (
            f"Nearby competitors ({names}) are also competing for the same customers online. "
            "Small improvements to your presence directly affect who gets found first."
        )
    else:
        competitor_note = "Local customers compare 2-3 options online before contacting anyone. Your online presence decides whether you make that shortlist."

    return {
        "headline": f"Online presence review for {lead.business_name}",
        "summary": (
            f"We reviewed the online presence of {lead.business_name}"
            + (f" in {lead.city}" if lead.city else "")
            + f". Current score: {lead.online_presence_score or 0}/100. "
            "Below are the specific items we found and what fixing each one would do for the business."
        ),
        "issues": issues[:5],
        "competitor_note": competitor_note,
        "recommendation": (
            "All of the items above are fixable quickly and affordably. "
            "I put this review together for you already; if it's useful, I'm happy to walk you through it in a 15-minute call, no strings attached."
        ),
    }


def _score_color(score: int) -> str:
    if score >= 70:
        return "#10b981"
    if score >= 40:
        return "#f59e0b"
    return "#ef4444"


def render_audit_html(lead, narrative: dict, sender: dict, analysis=None) -> str:
    e = html.escape
    score = int(lead.online_presence_score or 0)
    color = _score_color(score)
    today = date.today().strftime("%B %d, %Y")

    issues_html = ""
    for i, issue in enumerate(narrative.get("issues", []), 1):
        issues_html += f"""
        <div class="issue">
          <div class="issue-num">{i}</div>
          <div class="issue-body">
            <h3>{e(issue.get("title", ""))}</h3>
            <p class="impact"><strong>Why it matters:</strong> {e(issue.get("impact", ""))}</p>
            <p class="fix"><strong>The fix:</strong> {e(issue.get("fix", ""))}</p>
          </div>
        </div>"""

    tech_html = ""
    if analysis is not None:
        tech = analysis.tech_stack or {}
        tags = (tech.get("cms") or []) + (tech.get("frameworks") or []) + (tech.get("ecommerce") or [])
        if tags:
            chips = "".join(f'<span class="chip">{e(t)}</span>' for t in tags[:8])
            tech_html = f'<div class="section"><h2>Current technology</h2><div>{chips}</div></div>'

    sender_line = e(sender.get("my_name", ""))
    if sender.get("my_company"):
        sender_line += f" &middot; {e(sender['my_company'])}"
    contact_bits = []
    if sender.get("my_website"):
        contact_bits.append(f'<a href="{e(sender["my_website"])}">{e(sender["my_website"])}</a>')
    if sender.get("calendly_link"):
        contact_bits.append(f'<a href="{e(sender["calendly_link"])}">Book a free 15-min call</a>')
    contact_html = " &middot; ".join(contact_bits)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(narrative.get("headline", "Audit Report"))}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background: #f1f5f9; line-height: 1.6; }}
  .page {{ max-width: 760px; margin: 24px auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,.08); }}
  header {{ background: linear-gradient(135deg, #0f172a, #1e3a5f); color: #fff; padding: 40px 48px; }}
  header .label {{ text-transform: uppercase; letter-spacing: 2px; font-size: 11px; color: #94a3b8; margin-bottom: 8px; }}
  header h1 {{ font-size: 26px; line-height: 1.3; }}
  header .meta {{ margin-top: 10px; font-size: 13px; color: #cbd5e1; }}
  .score-row {{ display: flex; align-items: center; gap: 24px; padding: 32px 48px; border-bottom: 1px solid #e2e8f0; }}
  .score-ring {{ width: 108px; height: 108px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    background: conic-gradient({color} {score * 3.6}deg, #e2e8f0 0deg); flex-shrink: 0; }}
  .score-inner {{ width: 84px; height: 84px; border-radius: 50%; background: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
  .score-inner .n {{ font-size: 28px; font-weight: 800; color: {color}; }}
  .score-inner .d {{ font-size: 11px; color: #94a3b8; }}
  .summary {{ font-size: 15px; color: #334155; }}
  .section {{ padding: 28px 48px; border-bottom: 1px solid #e2e8f0; }}
  .section h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: 1.5px; color: #64748b; margin-bottom: 16px; }}
  .issue {{ display: flex; gap: 16px; margin-bottom: 20px; }}
  .issue-num {{ width: 28px; height: 28px; border-radius: 8px; background: #eff6ff; color: #2563eb; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-size: 14px; }}
  .issue-body h3 {{ font-size: 15px; margin-bottom: 4px; }}
  .issue-body p {{ font-size: 13.5px; color: #475569; margin-bottom: 3px; }}
  .issue-body .fix strong {{ color: #059669; }}
  .issue-body .impact strong {{ color: #b45309; }}
  .chip {{ display: inline-block; background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 999px; padding: 3px 12px; font-size: 12px; margin: 0 6px 6px 0; color: #475569; }}
  .note {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 12px; padding: 16px 20px; font-size: 13.5px; color: #713f12; }}
  .cta {{ padding: 32px 48px; background: #f8fafc; }}
  .cta p {{ font-size: 14.5px; color: #334155; margin-bottom: 14px; }}
  .cta .sender {{ font-weight: 700; color: #0f172a; }}
  .cta .links {{ font-size: 13.5px; }}
  .cta a {{ color: #2563eb; text-decoration: none; font-weight: 600; }}
  footer {{ text-align: center; font-size: 11px; color: #94a3b8; padding: 16px; }}
  @media print {{ body {{ background: #fff; }} .page {{ box-shadow: none; margin: 0; border-radius: 0; }} }}
</style>
</head>
<body>
<div class="page">
  <header>
    <div class="label">Free Online Presence Audit</div>
    <h1>{e(narrative.get("headline", ""))}</h1>
    <div class="meta">{e(lead.business_name)}{" &middot; " + e(lead.city) if lead.city else ""} &middot; {today}</div>
  </header>
  <div class="score-row">
    <div class="score-ring"><div class="score-inner"><span class="n">{score}</span><span class="d">of 100</span></div></div>
    <p class="summary">{e(narrative.get("summary", ""))}</p>
  </div>
  <div class="section">
    <h2>What we found</h2>
    {issues_html}
  </div>
  {tech_html}
  <div class="section">
    <h2>Your local market</h2>
    <div class="note">{e(narrative.get("competitor_note", ""))}</div>
  </div>
  <div class="cta">
    <p>{e(narrative.get("recommendation", ""))}</p>
    <p class="sender">{sender_line}</p>
    <p class="links">{contact_html}</p>
  </div>
  <footer>Prepared independently as a courtesy &middot; No obligation</footer>
</div>
</body>
</html>"""


async def generate_audit_report(lead, analysis, sender: dict, use_ai: bool = True) -> str:
    """Generate and save the audit report. Returns the public URL path."""
    from .ai_service import generate_audit_narrative

    narrative = None
    if use_ai:
        narrative = await generate_audit_narrative(lead, analysis, sender)
    if not narrative:
        narrative = _fallback_narrative(lead, analysis)

    html_doc = render_audit_html(lead, narrative, sender, analysis)

    os.makedirs(ASSETS_DIR, exist_ok=True)
    filename = f"audit_lead_{lead.id}.html"
    with open(os.path.join(ASSETS_DIR, filename), "w", encoding="utf-8") as f:
        f.write(html_doc)

    logger.info("Generated audit report for lead #%s (%s)", lead.id, lead.business_name)
    return f"/assets/{filename}"
