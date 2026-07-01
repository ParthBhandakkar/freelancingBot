import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup


SOCIAL_DOMAINS = {
    "facebook": ["facebook.com", "fb.com", "fb.me"],
    "instagram": ["instagram.com"],
    "linkedin": ["linkedin.com", "linkedin.in"],
    "twitter": ["twitter.com", "x.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
    "pinterest": ["pinterest.com", "pinterest.co.uk"],
    "github": ["github.com"],
    "behance": ["behance.net"],
    "dribbble": ["dribbble.com"],
    "medium": ["medium.com"],
    "whatsapp": ["wa.me", "whatsapp.com"],
}


def find_social_links(html: str, domain: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    found = {platform: [] for platform in SOCIAL_DOMAINS}

    all_links = soup.find_all("a", href=True)
    for link in all_links:
        href = link["href"].strip()
        parsed = urlparse(href)
        for platform, domains in SOCIAL_DOMAINS.items():
            for d in domains:
                if d in parsed.netloc or d in href:
                    found[platform].append(href)
                    break

    og_tags = soup.find_all("meta", attrs={"property": True})
    fb_match = re.search(r'https?://(?:www\.)?facebook\.com/[^"\'\s]+', html)
    if fb_match and not found["facebook"]:
        found["facebook"].append(fb_match.group())

    ig_match = re.search(r'https?://(?:www\.)?instagram\.com/[^"\'\s/]+', html)
    if ig_match and not found["instagram"]:
        found["instagram"].append(ig_match.group())

    li_match = re.search(r'https?://(?:www\.)?linkedin\.com/(?:company|in)/[^"\'\s]+', html)
    if li_match and not found["linkedin"]:
        found["linkedin"].append(li_match.group())

    result = {k: list(set(v)) for k, v in found.items() if v}
    return result


def estimate_social_metrics(social_links: dict) -> dict:
    metrics = {}
    if "instagram" in social_links:
        metrics["instagram_presence"] = True
    if "facebook" in social_links:
        metrics["facebook_presence"] = True
    if "linkedin" in social_links:
        metrics["linkedin_presence"] = True
    if "twitter" in social_links:
        metrics["twitter_presence"] = True
    if "youtube" in social_links:
        metrics["youtube_presence"] = True
    if "tiktok" in social_links:
        metrics["tiktok_presence"] = True

    platforms_found = sum(1 for v in metrics.values() if v)
    metrics["total_platforms"] = platforms_found
    metrics["social_presence_score"] = min(platforms_found * 15, 100)

    return metrics
