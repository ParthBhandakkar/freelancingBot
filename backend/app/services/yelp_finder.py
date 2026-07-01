import os
import httpx

DEFAULT_NICHES_YELP = {
    "bakery": "bakeries", "restaurant": "restaurants", "cafe": "coffee",
    "salon": "hair salons", "gym": "gyms", "grocery": "grocery",
    "pharmacy": "pharmacy", "dentist": "dentist", "laundry": "laundry",
    "bar": "bars", "clothing": "fashion", "electronics": "electronics",
    "hotel": "hotels", "photographer": "photographers", "real estate": "realestate",
    "lawyer": "lawyers", "doctor": "doctors", "tutor": "tutors",
    "yoga": "yoga", "florist": "florists", "pet store": "pets",
    "mechanic": "autorepair", "plumber": "plumbers",
}


async def find_businesses_yelp(city: str, niche: str = "", limit: int = 20) -> list[dict]:
    api_key = os.getenv("YELP_API_KEY", "")
    if not api_key:
        return []

    term = DEFAULT_NICHES_YELP.get(niche.lower(), niche) if niche else "business"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.yelp.com/v3/businesses/search",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"location": city, "term": term, "limit": min(limit, 50)},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
    except Exception:
        return []

    results = []
    for biz in data.get("businesses", []):
        results.append({
            "name": biz.get("name", ""),
            "business_name": biz.get("name", ""),
            "contact_name": "",
            "platform": "yelp",
            "niche": niche or biz.get("categories", [{}])[0].get("title", "").lower(),
            "city": city,
            "website_url": biz.get("url", ""),
            "phone": biz.get("display_phone", ""),
            "email": "",
            "address": " ".join(biz.get("location", {}).get("display_address", [])),
            "rating": biz.get("rating"),
            "total_ratings": biz.get("review_count", 0),
            "source": "yelp",
            "profile_url": biz.get("url", ""),
            "image_url": biz.get("image_url", ""),
            "yelp_rating": biz.get("rating"),
            "yelp_reviews": biz.get("review_count", 0),
            "price_range": biz.get("price", ""),
        })

    return results
