from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..models import Lead
from ..schemas import LeadCreate, LeadOut
from ..services.lead_finder import find_businesses
import httpx
from bs4 import BeautifulSoup

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/analyze-website")
async def analyze_website(url: str = Query(...)):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

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

        return {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "score": score,
            "issues": issues,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to analyze website: {str(e)}")


@router.get("/find")
async def search_businesses(
    city: str = Query(..., description="City name"),
    niche: str = Query("", description="Business type (bakery, salon, gym, etc.)"),
    limit: int = Query(20, ge=1, le=50),
):
    """Find businesses. Tries Google Places first (if key set), always falls back to sample data."""
    try:
        results = await find_businesses(city, niche, limit, use_sample=True)
        source = results[0].get("source", "sample_data") if results else "sample_data"
        return {
            "city": city,
            "niche": niche,
            "total": len(results),
            "source_type": source,
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find businesses: {str(e)}")


@router.get("/niches")
def list_niches():
    """List all supported business niches."""
    from ..services.lead_finder import DEFAULT_NICHES
    return {"default_niches": DEFAULT_NICHES}


@router.post("/add-from-search", response_model=LeadOut)
def add_lead_from_search(data: LeadCreate, db: Session = Depends(get_db)):
    lead = Lead(**data.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead
