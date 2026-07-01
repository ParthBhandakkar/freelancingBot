from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..models import Lead
from ..schemas import LeadCreate, LeadOut
from ..services.lead_finder import find_businesses, enrich_search_results, DEFAULT_NICHES
from ..services.tech_analyzer import detect_tech_stack
from ..services.social_auditor import find_social_links, estimate_social_metrics
from ..services.competitor_finder import find_competitors_google_places
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/analyze-website")
async def analyze_website(url: str = Query(...), deep: bool = Query(False)):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html_text = resp.text
            soup = BeautifulSoup(html_text, "lxml")

        title = soup.title.string.strip() if soup.title and soup.title.string else "No title"
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"][:300]

        issues = []
        if not soup.find("meta", attrs={"name": "viewport"}):
            issues.append("Not mobile-friendly (missing viewport meta tag)")
        if not soup.find("link", rel="icon"):
            issues.append("Missing favicon")
        if not soup.find_all("img", alt=True):
            issues.append("Images missing alt text (bad for SEO)")
        slow_indicators = sum(1 for s in soup.find_all(["script", "link"]) if s.get("src", "") or s.get("href", ""))
        if slow_indicators > 30:
            issues.append(f"High number of external resources ({slow_indicators}) may slow load time")
        if not soup.find("meta", attrs={"property": "og:title"}):
            issues.append("Missing Open Graph meta tags (bad for social sharing)")

        score = 100
        score -= len(issues) * 10
        score = max(0, min(100, score))

        result = {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "score": score,
            "issues": issues,
        }

        if deep:
            result["tech_stack"] = detect_tech_stack(html_text)
            result["social_links"] = find_social_links(html_text, url)
            result["social_metrics"] = estimate_social_metrics(result["social_links"])

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to analyze website: {str(e)}")


@router.get("/find")
async def search_businesses(
    city: str = Query(..., description="City name"),
    niche: str = Query("", description="Business type (bakery, salon, gym, etc.)"),
    limit: int = Query(20, ge=1, le=50),
    source: str = Query("auto", description="Data source: auto, google, yelp, sample"),
):
    """Find businesses. Tries multiple sources and returns enriched results."""
    try:
        if source == "google":
            from ..services.lead_finder import find_by_google_places
            results = await find_by_google_places(city, niche, limit)
        elif source == "yelp":
            from ..services.yelp_finder import find_businesses_yelp
            results = await find_businesses_yelp(city, niche, limit)
        else:
            results = await find_businesses(city, niche, limit, use_sample=True)

        enriched = enrich_search_results(results)

        source_type = enriched[0].get("source", "sample_data") if enriched else "none"
        return {
            "city": city,
            "niche": niche,
            "total": len(enriched),
            "source_type": source_type,
            "results": enriched,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find businesses: {str(e)}")


@router.get("/find-competitors")
async def search_competitors(
    niche: str = Query(...),
    city: str = Query(...),
    exclude: str = Query(""),
    limit: int = Query(10, ge=1, le=30),
):
    """Find competitors for a business in a city."""
    try:
        competitors = await find_competitors_google_places(niche, city, exclude, limit)
        return {
            "niche": niche,
            "city": city,
            "total": len(competitors),
            "results": competitors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find competitors: {str(e)}")


@router.get("/niches")
def list_niches():
    """List all supported business niches."""
    return {"default_niches": DEFAULT_NICHES}


@router.post("/add-from-search", response_model=LeadOut)
def add_lead_from_search(data: LeadCreate, db: Session = Depends(get_db)):
    lead = Lead(**data.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
