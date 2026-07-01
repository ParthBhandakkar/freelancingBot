from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Lead, LeadAnalysis
from ..schemas import LeadAnalysisOut
from ..services.tech_analyzer import detect_tech_stack
from ..services.social_auditor import find_social_links, estimate_social_metrics
from ..services.contact_enricher import guess_emails, find_email_via_hunter
from ..services.review_miner import score_keywords
from ..services.competitor_finder import find_competitors_google_places
import httpx
from bs4 import BeautifulSoup

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/analyze-lead/{lead_id}", response_model=LeadAnalysisOut)
async def analyze_lead_full(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    existing = db.query(LeadAnalysis).filter(LeadAnalysis.lead_id == lead_id).first()
    if existing:
        db.delete(existing)
        db.commit()

    tech_stack = {}
    social_links = {}
    social_metrics = {}
    contact_emails = []
    review_signals = []
    competitor_data = {}
    html_text = ""
    domain = ""

    target_url = lead.website_url or lead.profile_url or ""
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

                    meta_desc = soup.find("meta", attrs={"name": "description"})
                    if meta_desc and meta_desc.get("content"):
                        review_signals = [
                            score_keywords(meta_desc["content"])
                        ]

                    from urllib.parse import urlparse
                    parsed = urlparse(target_url)
                    domain = parsed.netloc.replace("www.", "")

                    guessed = await guess_emails(domain, lead.business_name, lead.name)
                    contact_emails = guessed

                    hunter_emails, _ = await find_email_via_hunter(domain)
                    if hunter_emails:
                        contact_emails = list(set(contact_emails + hunter_emails))
        except Exception:
            pass

    if lead.niche and lead.city:
        comps = await find_competitors_google_places(lead.niche, lead.city, lead.business_name)
        competitor_data = {
            "competitors": comps[:5],
            "total_found": len(comps),
        }

    flaws_text = lead.flaws or ""
    keyword_data = score_keywords(flaws_text)
    if keyword_data["score"] > 0:
        lead.lead_score = keyword_data["score"]
        lead.intent_signals = ", ".join(s["keyword"] for s in keyword_data["signals"])
        db.commit()

    analysis = LeadAnalysis(
        lead_id=lead_id,
        tech_stack=tech_stack,
        social_links=social_links,
        social_metrics=social_metrics,
        contact_email=contact_emails[0] if contact_emails else "",
        contact_phone=lead.phone or "",
        competitor_insights=competitor_data,
        keyword_signals=keyword_data.get("signals", []),
    )

    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


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
