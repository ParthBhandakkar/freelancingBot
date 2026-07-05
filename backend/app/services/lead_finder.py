import os
import re
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from ..models import Lead

DEFAULT_NICHES = [
    "bakery", "restaurant", "cafe", "salon", "gym", "grocery",
    "pharmacy", "dentist", "laundry", "bar", "clothing", "electronics",
    "hotel", "photographer", "real estate", "lawyer", "doctor",
    "tutor", "yoga", "florist", "pet store", "mechanic", "plumber",
]


async def find_by_google_places(city: str, niche: str = "", limit: int = 20) -> list[dict]:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return []

    query = f"{niche} in {city}" if niche else f"business in {city}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={"query": query, "key": api_key})
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    if data.get("status") != "OK":
        return []

    results = []
    for place in data.get("results", [])[:limit]:
        name = place.get("name", "")
        if not name:
            continue

        place_id = place.get("place_id", "")
        address = place.get("formatted_address", "")
        rating = place.get("rating")
        total_ratings = place.get("user_ratings_total", 0)
        types = place.get("types", [])

        website = ""
        phone = ""
        if place_id:
            try:
                detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
                detail_resp = await client.get(
                    detail_url,
                    params={"place_id": place_id, "fields": "website,formatted_phone_number", "key": api_key},
                )
                result = detail_resp.json().get("result", {})
                website = result.get("website", "")
                phone = result.get("formatted_phone_number", "")
            except Exception:
                pass

        results.append({
            "name": name,
            "business_name": name,
            "contact_name": "",
            "platform": "google_maps",
            "niche": types[0] if types else niche,
            "city": city,
            "website_url": website,
            "phone": phone,
            "email": "",
            "address": address,
            "rating": rating,
            "total_ratings": total_ratings,
            "source": "google_places",
            "profile_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else "",
        })

    return results


async def find_businesses(city: str, niche: str = "", limit: int = 20) -> list[dict]:
    results = await find_by_google_places(city, niche, limit)
    if results:
        return results

    from .yelp_finder import find_businesses_yelp
    yelp_results = await find_businesses_yelp(city, niche, limit)
    if yelp_results:
        return yelp_results

    return []


def calc_lead_potential(biz: dict) -> dict:
    score = 0
    signals = []

    no_website = not biz.get("website_url")
    if no_website:
        score += 35
        signals.append("No website (hot lead)")

    has_phone = bool(biz.get("phone"))
    has_email = bool(biz.get("email"))
    if has_phone and not has_email:
        score += 15
        signals.append("Has phone, no email")
    if not has_phone and not has_email:
        score += 10
        signals.append("No contact info found")

    reviews = biz.get("total_ratings") or 0
    rating = biz.get("rating") or 0
    if reviews > 100:
        score += 15
        signals.append(f"Established ({reviews} reviews)")
    elif reviews > 30:
        score += 10
        signals.append(f"Growing ({reviews} reviews)")
    if rating >= 4.5 and reviews > 20:
        score += 5
        signals.append("Highly rated")

    text_to_check = " ".join([
        str(biz.get("name", "")),
        str(biz.get("types", [])),
        str(biz.get("address", "")),
    ]).lower()

    intent_kws = ["need", "looking for", "new business", "just started", "growing", "expanding"]
    matches = [kw for kw in intent_kws if kw in text_to_check]
    if matches:
        score += min(len(matches) * 10, 20)
        signals.extend(matches)

    score = min(score, 100)
    return {"potential_score": score, "signals": signals}


def find_existing_leads(results: list[dict], db: Session) -> set:
    existing = set()
    for biz in results:
        name = (biz.get("business_name") or biz.get("name") or "").strip()
        city = (biz.get("city") or "").strip()
        website = (biz.get("website_url") or "").strip()
        if not name:
            continue

        dup = db.query(Lead).filter(Lead.business_name.ilike(f"%{name}%"))
        if city:
            dup = dup.filter(Lead.city.ilike(f"%{city}%"))
        if dup.first():
            existing.add(name)
            continue

        if website:
            dup = db.query(Lead).filter(Lead.website_url.ilike(website)).first()
            if dup:
                existing.add(name)

    return existing


def enrich_search_results(results: list[dict], existing_names: set = None) -> list[dict]:
    enriched = []
    existing = existing_names or set()
    for biz in results:
        biz_copy = dict(biz)
        potential = calc_lead_potential(biz)
        biz_copy["potential_score"] = potential["potential_score"]
        biz_copy["potential_signals"] = potential["signals"]
        name_check = biz.get("name", "") in existing or biz.get("business_name", "") in existing
        biz_copy["already_imported"] = name_check
        enriched.append(biz_copy)

    enriched.sort(key=lambda x: (x.get("already_imported", False), -x.get("potential_score", 0)))
    return enriched
