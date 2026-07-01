import os
import httpx
import random

DEFAULT_NICHES = [
    "bakery", "restaurant", "cafe", "salon", "gym", "grocery",
    "pharmacy", "dentist", "laundry", "bar", "clothing", "electronics",
    "hotel", "photographer", "real estate", "lawyer", "doctor",
    "tutor", "yoga", "florist", "pet store", "mechanic", "plumber",
]


async def find_competitors_google_places(
    niche: str, city: str, exclude_name: str = "", limit: int = 10
) -> list[dict]:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return _generate_mock_competitors(niche, city, exclude_name, limit)

    query = f"{niche} in {city}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": api_key},
            )
            data = resp.json()
    except Exception:
        return _generate_mock_competitors(niche, city, exclude_name, limit)

    if data.get("status") != "OK":
        return _generate_mock_competitors(niche, city, exclude_name, limit)

    competitors = []
    for place in data.get("results", []):
        name = place.get("name", "")
        if not name or (exclude_name and exclude_name.lower() in name.lower()):
            continue
        competitors.append({
            "name": name,
            "address": place.get("formatted_address", ""),
            "rating": place.get("rating"),
            "total_ratings": place.get("user_ratings_total", 0),
            "types": place.get("types", []),
            "source": "google_places",
        })
        if len(competitors) >= limit:
            break

    return competitors


def _generate_mock_competitors(niche: str, city: str, exclude_name: str = "", count: int = 8) -> list[dict]:
    prefixes = ["The", "Royal", "Star", "Prime", "Elite", "Golden", "Silver", "Modern", "Classic", "Best"]
    labels_map = {
        "bakery": ["Bakery", "Bakers", "Patisserie", "Cake Shop"],
        "restaurant": ["Restaurant", "Dining", "Eatery", "Bistro"],
        "salon": ["Salon", "Beauty Parlour", "Hair Studio", "Spa"],
        "gym": ["Gym", "Fitness Centre", "Wellness Center"],
        "cafe": ["Cafe", "Coffee House", "Coffee Shop", "Brew"],
    }
    labels = labels_map.get(niche.lower(), [niche.title(), niche.title() + " Shop", niche.title() + " House"])

    results = []
    for i in range(count):
        name = f"{random.choice(prefixes)} {random.choice(labels)}"
        if exclude_name and exclude_name.lower() in name.lower():
            name = f"{name} {i+1}"
        results.append({
            "name": name,
            "address": f"{random.randint(1,999)}, {random.choice(['Main St', 'Market Rd', 'Park Ave'])}, {city}",
            "rating": round(random.uniform(3.0, 5.0), 1),
            "total_ratings": random.randint(5, 300),
            "source": "sample_data",
        })
    return results
