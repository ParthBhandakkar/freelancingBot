import os
import httpx


async def find_competitors_google_places(
    niche: str, city: str, exclude_name: str = "", limit: int = 10
) -> list[dict]:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        return []

    query = f"{niche} in {city}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://maps.googleapis.com/maps/api/place/textsearch/json",
                params={"query": query, "key": api_key},
            )
            data = resp.json()
    except Exception:
        return []

    if data.get("status") != "OK":
        return []

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
