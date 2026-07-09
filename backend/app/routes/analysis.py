import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Lead, LeadAnalysis
from ..schemas import LeadAnalysisOut, DeepAnalysisOut
from ..services.tech_analyzer import detect_tech_stack
from ..services.social_auditor import find_social_links, estimate_social_metrics
from ..services.contact_enricher import find_email_via_hunter
from ..services.email_scraper import scrape_emails_from_website
from ..services.review_miner import score_keywords
from ..services.competitor_finder import find_competitors_google_places
from ..services.channels import determine_channel
from ..services.settings_service import get_sender_identity
from ..services.audit_generator import generate_audit_report
from ..services.ollama_service import check_ollama_running, fetch_website_text, run_deep_analysis
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

SITE_ISSUE_CHECKS = [
    (lambda soup: not soup.find("meta", attrs={"name": "viewport"}), "Not mobile-friendly (missing viewport meta tag)"),
    (lambda soup: not soup.find("link", rel="icon"), "Missing favicon"),
    (lambda soup: not soup.find("meta", attrs={"name": "description"}), "Missing meta description (hurts Google ranking)"),
    (lambda soup: not soup.find("meta", attrs={"property": "og:title"}), "Missing Open Graph tags (bad link previews when shared)"),
    (lambda soup: not soup.find("h1"), "No main heading (H1) on homepage (bad for SEO)"),
]


async def run_full_analysis(lead: Lead, db: Session) -> LeadAnalysis:
    """Fetch the lead's site, detect tech/social, scrape real emails, find
    competitors, compute score + channel, and persist a LeadAnalysis row.

    Shared by the analyze endpoint, the one-click import flow, and re-enrichment.
    """
    existing = db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == lead.id).first()
    if existing:
        db.delete(existing)
        db.commit()

    tech_stack = {}
    social_links = {}
    social_metrics = {}
    contact_emails = []
    review_signals = []
    competitor_data = {}
    site_issues = []
    domain = ""

    target_url = lead.website_url or ""
    if target_url:
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(target_url)
                if resp.status_code == 200:
                    html_text = resp.text
                    soup = BeautifulSoup(html_text, "lxml")

                    tech_stack = detect_tech_stack(html_text)
                    social_links = find_social_links(html_text, target_url)
                    social_metrics = estimate_social_metrics(social_links)

                    for check, message in SITE_ISSUE_CHECKS:
                        try:
                            if check(soup):
                                site_issues.append(message)
                        except Exception:
                            pass

                    meta_desc = soup.find("meta", attrs={"name": "description"})
                    if meta_desc and meta_desc.get("content"):
                        review_signals = [score_keywords(meta_desc["content"])]
                        lead.analysis_notes = meta_desc["content"][:500]

                    from urllib.parse import urlparse
                    parsed = urlparse(str(resp.url))
                    domain = parsed.netloc.replace("www.", "")
        except Exception as e:
            logger.warning("Site fetch failed for lead #%s (%s): %s", lead.id, target_url, e)

        # Real email discovery: crawl the site for mailto:/email patterns
        scraped = await scrape_emails_from_website(target_url)
        contact_emails = scraped

        # Hunter.io as optional supplement
        if domain and not contact_emails:
            hunter_emails, _ = await find_email_via_hunter(domain)
            if hunter_emails:
                contact_emails = hunter_emails

    if lead.niche and lead.city:
        try:
            comps = await find_competitors_google_places(lead.niche, lead.city, lead.business_name)
            competitor_data = {"competitors": comps[:5], "total_found": len(comps)}
        except Exception:
            competitor_data = {}

    # Update the lead itself with what we learned
    if contact_emails and not lead.email:
        lead.email = contact_emails[0]

    if site_issues and not lead.flaws:
        lead.flaws = "\n".join(site_issues)

    if target_url:
        score = max(0, min(100, 100 - len(site_issues) * 12))
        lead.online_presence_score = score
    else:
        lead.online_presence_score = 0

    keyword_data = score_keywords(lead.flaws or "")
    if keyword_data["score"] > 0:
        lead.lead_score = max(lead.lead_score or 0, keyword_data["score"])
        lead.intent_signals = ", ".join(s["keyword"] for s in keyword_data["signals"])

    lead.channel = determine_channel(
        email=lead.email or "",
        phone=lead.phone or "",
        social_links=social_links,
        profile_url=lead.profile_url or "",
    )

    analysis = LeadAnalysis(
        lead_id=lead.id,
        tech_stack=tech_stack,
        social_links=social_links,
        social_metrics=social_metrics,
        review_snippets=[{"emails_found": contact_emails[:5]}] if contact_emails else [],
        contact_email=contact_emails[0] if contact_emails else "",
        contact_phone=lead.phone or "",
        competitor_insights=competitor_data,
        keyword_signals=keyword_data.get("signals", []),
    )

    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    db.refresh(lead)
    logger.info(
        "Analyzed lead #%s: emails=%d channel=%s score=%s",
        lead.id, len(contact_emails), lead.channel, lead.online_presence_score,
    )
    return analysis


@router.post("/analyze-lead/{lead_id}", response_model=LeadAnalysisOut)
async def analyze_lead_full(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await run_full_analysis(lead, db)


@router.post("/generate-audit/{lead_id}")
async def generate_audit(lead_id: int, use_ai: bool = Query(True), db: Session = Depends(get_db)):
    """Generate a shareable HTML audit report for this lead (the 'send proof' asset)."""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    analysis = db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == lead_id).first()
    if analysis is None:
        analysis = await run_full_analysis(lead, db)

    sender = get_sender_identity(db)
    url = await generate_audit_report(lead, analysis, sender, use_ai=use_ai)

    lead.asset_generated = True
    lead.asset_url = url
    db.commit()

    return {"asset_url": url, "lead_id": lead.id}


@router.post("/re-enrich-all")
async def re_enrich_all(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    """Backfill website/phone/email for existing leads that have none.

    Fixes leads imported while the Google Places details bug was live: re-searches
    each lead by name+city to recover website/phone, then re-runs full analysis.
    """
    from ..services.lead_finder import find_by_google_places

    leads = (
        db.query(Lead)
        .filter((Lead.website_url == "") | (Lead.website_url.is_(None)))
        .filter((Lead.phone == "") | (Lead.phone.is_(None)))
        .limit(limit)
        .all()
    )

    updated = 0
    analyzed = 0
    for lead in leads:
        try:
            results = await find_by_google_places(lead.city or "", lead.business_name, limit=3)
            match = next(
                (r for r in results if r["name"].lower().strip() == lead.business_name.lower().strip()),
                results[0] if results else None,
            )
            if match:
                if match.get("website_url") and not lead.website_url:
                    lead.website_url = match["website_url"]
                    updated += 1
                if match.get("phone") and not lead.phone:
                    lead.phone = match["phone"]
                if match.get("rating") and not lead.rating:
                    lead.rating = match["rating"]
                    lead.total_ratings = match.get("total_ratings", 0)
                db.commit()
            await run_full_analysis(lead, db)
            analyzed += 1
        except Exception as e:
            logger.warning("Re-enrich failed for lead #%s: %s", lead.id, e)

    return {"processed": len(leads), "recovered_websites": updated, "analyzed": analyzed}


@router.get("/lead/{lead_id}", response_model=LeadAnalysisOut)
def get_lead_analysis(lead_id: int, db: Session = Depends(get_db)):
    analysis = db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == lead_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this lead")
    return analysis


@router.delete("/lead/{lead_id}")
def delete_lead_analysis(lead_id: int, db: Session = Depends(get_db)):
    analysis = db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == lead_id).first()
    if analysis:
        db.delete(analysis)
        db.commit()
    return {"message": "Analysis deleted"}


@router.get("/ollama-status")
async def ollama_status():
    running = await check_ollama_running()
    return {"running": running}


@router.post("/deep-analysis/{lead_id}", response_model=DeepAnalysisOut)
async def deep_analysis_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    ollama_ok = await check_ollama_running()
    if not ollama_ok:
        return DeepAnalysisOut(
            recommendations=[],
            analysis_summary="",
            pain_points=[],
            opportunities=[],
            error="OLLAMA model is not running. Please start OLLAMA with 'ollama serve' and ensure the model is available.",
        )

    website_text = await fetch_website_text(lead.website_url or "")

    social_context_parts = []
    if lead.profile_url:
        social_context_parts.append(f"Profile URL: {lead.profile_url}")
    analysis = db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == lead.id).first()
    if analysis:
        if analysis.social_links:
            social_context_parts.append(f"Social Links: {json.dumps(analysis.social_links)}")
        if analysis.social_metrics:
            social_context_parts.append(f"Social Metrics: {json.dumps(analysis.social_metrics)}")
        if analysis.tech_stack:
            social_context_parts.append(f"Tech Stack: {json.dumps(analysis.tech_stack)}")
        if analysis.competitor_insights:
            social_context_parts.append(f"Competitors: {json.dumps(analysis.competitor_insights)}")
    social_context = "\n".join(social_context_parts)

    lead_data = {
        "name": lead.name,
        "business_name": lead.business_name,
        "city": lead.city or "",
        "niche": lead.niche or "",
        "website_url": lead.website_url or "",
        "online_presence_score": lead.online_presence_score or 0,
        "lead_score": lead.lead_score or 0,
    }

    result = await run_deep_analysis(lead_data, website_text, social_context)

    return DeepAnalysisOut(
        recommendations=result.get("recommendations", []),
        analysis_summary=result.get("analysis_summary", ""),
        pain_points=result.get("pain_points", []),
        opportunities=result.get("opportunities", []),
        error=result.get("error"),
    )
