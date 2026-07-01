import os
import re
import httpx

COMMON_EMAIL_PATTERNS = [
    "info@{domain}",
    "contact@{domain}",
    "hello@{domain}",
    "admin@{domain}",
    "support@{domain}",
    "sales@{domain}",
    "business@{domain}",
    "connect@{domain}",
    "enquiry@{domain}",
]

NAME_PATTERNS = [
    "{first}@{domain}",
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{first}@{domain}",
]


async def guess_emails(domain: str, business_name: str = "", contact_name: str = "") -> list[str]:
    domain = domain.lower().strip()
    if not domain.startswith("http"):
        domain = "https://" + domain
    parsed = re.sub(r"https?://(?:www\.)?", "", domain).split("/")[0]
    domain = parsed

    guesses = []
    for pattern in COMMON_EMAIL_PATTERNS:
        guesses.append(pattern.format(domain=domain))

    if contact_name:
        parts = contact_name.strip().split()
        first = parts[0].lower() if parts else ""
        last = parts[-1].lower() if len(parts) > 1 else ""
        if first:
            guesses.append(f"{first}@{domain}")
        if first and last:
            guesses.append(f"{first}.{last}@{domain}")
            guesses.append(f"{first}{last}@{domain}")

    return list(set(guesses))


async def find_email_via_hunter(domain: str, api_key: str = "") -> tuple[list[str], list[str]]:
    key = api_key or os.getenv("HUNTER_API_KEY", "")
    if not key:
        return [], []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.hunter.io/v2/domain-search",
                params={"domain": domain, "api_key": key},
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                emails = [e["value"] for e in data.get("emails", [])]
                return emails, []
            return [], [f"Hunter API error: {resp.status_code}"]
    except Exception as e:
        return [], [str(e)]
