import os
import re
import httpx
import random
from typing import Optional

DEFAULT_NICHES = [
    "bakery", "restaurant", "cafe", "salon", "gym", "grocery",
    "pharmacy", "dentist", "laundry", "bar", "clothing", "electronics",
    "hotel", "photographer", "real estate", "lawyer", "doctor",
    "tutor", "yoga", "florist", "pet store", "mechanic", "plumber",
]

CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
    "New York", "Los Angeles", "Chicago", "London", "Toronto",
    "Dubai", "Singapore", "Sydney", "Berlin", "Paris",
]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Anaya", "Diya", "Myra", "Sara", "Aanya", "Aadhya",
    "Neha", "Priya", "Anita", "Ravi", "Vikram", "Raj", "Amit", "Sunita"]

BUSINESS_PREFIXES = ["The", "Shri", "Royal", "New", "Star", "City", "Prime", "Elite",
    "Golden", "Silver", "Modern", "Classic", "Fresh", "Green", "Best"]


def _generate_mock_businesses(city: str, niche: str, count: int = 20) -> list[dict]:
    """Generate realistic-looking sample businesses for demo/testing purposes."""
    niches = [niche] if niche else DEFAULT_NICHES
    results = []
    seen_names = set()
    niche_labels = {
        "bakery": ["Bakery", "Bakers", "Patisserie", "Cake Shop", "Bread House"],
        "restaurant": ["Restaurant", "Dining", "Food Point", "Eatery", "Bistro"],
        "cafe": ["Cafe", "Coffee House", "Coffee Shop", "Tea House", "Brew"],
        "salon": ["Salon", "Unisex Salon", "Beauty Parlour", "Hair Studio", "Spa"],
        "gym": ["Gym", "Fitness Centre", "Fitness Studio", "Wellness Center", "Training Hub"],
        "grocery": ["Supermarket", "Grocery Store", "Department Store", "Mart", "General Store"],
        "pharmacy": ["Pharmacy", "Medical Store", "Chemist", "Medi-Care", "Drug Store"],
        "dentist": ["Dental Clinic", "Dentist", "Dental Care", "Smile Studio", "Dental Hospital"],
        "doctor": ["Clinic", "Medical Centre", "Health Care", "Hospital", "Wellness Clinic"],
        "hotel": ["Hotel", "Residency", "Inn", "Guest House", "Lodge"],
        "bar": ["Bar", "Pub", "Lounge", "Wine Shop", "Microbrewery"],
        "electronics": ["Electronics", "Digital Mart", "Gadget Store", "Mobile Point", "Tech Hub"],
        "clothing": ["Fashion Store", "Clothing", "Garments", "Boutique", "Trends"],
        "laundry": ["Laundry", "Dry Cleaners", "Wash & Fold", "Launderette", "Clean Home"],
        "florist": ["Flowers", "Florist", "Flower Shop", "Petals", "Blooms"],
        "pet store": ["Pet Store", "Pet Shop", "Pet Care", "Animal Hub", "Pets World"],
        "mechanic": ["Auto Repair", "Garage", "Car Service", "Mechanic Shop", "Auto Care"],
        "photographer": ["Photography", "Studio", "Photo House", "Captures", "Lens Studio"],
        "real estate": ["Reality", "Estate Agents", "Properties", "Homes", "Realtors"],
        "tutor": ["Tuition Centre", "Academy", "Learning Hub", "Tutorials", "Education Centre"],
        "yoga": ["Yoga Centre", "Yoga Studio", "Wellness Hub", "Meditation Centre", "Fitness Yoga"],
    }

    labels = niche_labels.get(niche.lower(), [niche.title(), niche.title() + " Shop", niche.title() + " Centre", niche.title() + " House", niche.title() + " Hub"])

    for i in range(count):
        prefix = random.choice(BUSINESS_PREFIXES) if random.random() > 0.3 else ""
        label = random.choice(labels)
        name_parts = [p for p in [prefix, label] if p]
        business_name = " ".join(name_parts)
        if random.random() > 0.5:
            business_name = f"{business_name} {random.choice(['', city]).strip()}".strip()
        if business_name.lower() in seen_names:
            business_name = f"{business_name} {i+1}"
        seen_names.add(business_name.lower())

        first_name = random.choice(FIRST_NAMES)
        contact_name = first_name
        phone = f"+91-{random.randint(70000, 99999)}-{random.randint(10000, 99999)}"
        website = business_name.lower().replace(" ", "").replace("&", "and") + ".com"
        website = re.sub(r'[^a-z0-9.]', '', website)

        results.append({
            "name": business_name,
            "business_name": business_name,
            "contact_name": contact_name,
            "platform": "website",
            "niche": niche or random.choice(niches),
            "city": city,
            "website_url": f"https://www.{website}",
            "phone": phone,
            "email": f"contact@{website}",
            "address": f"{random.randint(1, 999)}, {random.choice(['Main Road', 'Market Road', 'Station Road', 'MG Road', 'Park Street'])}, {city}",
            "rating": round(random.uniform(3.0, 5.0), 1),
            "total_ratings": random.randint(10, 500),
            "source": "sample_data",
            "profile_url": "",
        })

    return results


async def find_by_google_places(city: str, niche: str = "", limit: int = 20) -> list[dict]:
    """Find real businesses using Google Places API.
    
    To use: Get a free API key from https://console.cloud.google.com
    1. Create a project
    2. Enable 'Places API' 
    3. Create credentials (API key)
    4. Set GOOGLE_API_KEY environment variable
    """
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


async def find_businesses(city: str, niche: str = "", limit: int = 20, use_sample: bool = True) -> list[dict]:
    """Find businesses using Google Places API. Falls back to sample data if unavailable."""
    results = await find_by_google_places(city, niche, limit)
    if results:
        return results
    return _generate_mock_businesses(city, niche, min(limit, 20))
