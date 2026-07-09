import re
import logging
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Pages most likely to list a contact email
CONTACT_PATHS = ["/contact", "/contact-us", "/contactus", "/about", "/about-us", "/impressum"]

# Junk domains/patterns that regexes pick up but are never real contact emails
JUNK_DOMAINS = (
    "example.com", "sentry.io", "wixpress.com", "sentry.wixpress.com",
    "domain.com", "email.com", "yourdomain.com", "godaddy.com",
    "sentry-next.wixpress.com", "mysite.com", "site.com",
)
JUNK_PREFIXES = ("noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".css", ".js")


def _clean_emails(raw: set[str], site_domain: str = "") -> list[str]:
    cleaned = []
    for email in raw:
        email = email.strip().strip(".").lower()
        if any(email.endswith(ext) for ext in IMAGE_EXTENSIONS):
            continue
        domain = email.split("@")[-1]
        if domain in JUNK_DOMAINS:
            continue
        local = email.split("@")[0]
        if any(local.startswith(p) for p in JUNK_PREFIXES):
            continue
        if len(email) > 100:
            continue
        cleaned.append(email)

    # Prefer emails on the business's own domain, then generic providers
    def rank(e: str) -> int:
        d = e.split("@")[-1]
        if site_domain and (d == site_domain or d.endswith("." + site_domain)):
            return 0
        if d in ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"):
            return 1
        return 2

    return sorted(set(cleaned), key=rank)


def _extract_emails_from_html(html: str) -> set[str]:
    found = set()
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if addr:
                found.add(addr)
    found.update(EMAIL_RE.findall(html))
    return found


async def scrape_emails_from_website(website_url: str, max_pages: int = 4) -> list[str]:
    """Crawl a business website's homepage + likely contact pages for real email addresses.

    Returns a ranked list (own-domain emails first). Never raises.
    """
    if not website_url:
        return []
    if not website_url.startswith(("http://", "https://")):
        website_url = "https://" + website_url

    parsed = urlparse(website_url)
    site_domain = parsed.netloc.replace("www.", "")
    found: set[str] = set()

    urls_to_try = [website_url]
    base = f"{parsed.scheme}://{parsed.netloc}"

    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LeadFinderBot/1.0)"},
        ) as client:
            # Fetch homepage first; discover contact-page links from it
            try:
                resp = await client.get(website_url)
                if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", "text/html"):
                    found.update(_extract_emails_from_html(resp.text))
                    soup = BeautifulSoup(resp.text, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"].lower()
                        text = (a.get_text() or "").lower()
                        if any(kw in href or kw in text for kw in ("contact", "about", "reach us", "get in touch")):
                            full = urljoin(website_url, a["href"])
                            if urlparse(full).netloc == parsed.netloc and full not in urls_to_try:
                                urls_to_try.append(full)
            except Exception:
                pass

            # Add common contact paths as fallbacks
            for path in CONTACT_PATHS:
                candidate = base + path
                if candidate not in urls_to_try:
                    urls_to_try.append(candidate)

            # If homepage already yielded an own-domain email we can stop early
            for url in urls_to_try[1:max_pages + 1]:
                ranked = _clean_emails(found, site_domain)
                if ranked and ranked[0].split("@")[-1].endswith(site_domain):
                    break
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", "text/html"):
                        found.update(_extract_emails_from_html(resp.text))
                except Exception:
                    continue
    except Exception as e:
        logger.warning("Email scrape failed for %s: %s", website_url, e)

    result = _clean_emails(found, site_domain)
    if result:
        logger.info("Scraped %d email(s) from %s: %s", len(result), site_domain, result[:3])
    return result
