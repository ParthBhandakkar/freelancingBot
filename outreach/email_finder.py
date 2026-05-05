"""Email finder using Hunter.io API.

Given a full name and company domain, attempts to find a verified business email.
Degrades gracefully when API key is missing or rate limits are hit.
"""
from __future__ import annotations

import asyncio
import json
from urllib.error import HTTPError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

from loguru import logger

from config import settings


HUNTER_FINDER_URL = "https://api.hunter.io/v2/email-finder"
HUNTER_VERIFIER_URL = "https://api.hunter.io/v2/email-verifier"


class EmailFinder:
    """Find business emails via Hunter.io API."""

    def __init__(self) -> None:
        self._daily_count = 0

    @property
    def available(self) -> bool:
        return settings.has_hunter_key

    async def find_email(
        self,
        full_name: str,
        company: str,
        domain: str = "",
    ) -> str | None:
        """Find an email address for a person at a company.

        Returns the email string or None if not found / unavailable.
        """
        if not self.available:
            return None

        if not full_name or not (company or domain):
            return None

        target_domain = domain or self._guess_domain(company)
        if not target_domain:
            return None

        try:
            result = await asyncio.to_thread(
                self._hunter_find, full_name, target_domain
            )
            return result
        except Exception as exc:
            logger.debug("Email finder failed for {} at {}: {}", full_name, target_domain, exc)
            return None

    def _hunter_find(self, full_name: str, domain: str) -> str | None:
        """Call Hunter.io email-finder endpoint."""
        names = full_name.strip().split(" ", maxsplit=1)
        first_name = names[0] if names else ""
        last_name = names[1] if len(names) > 1 else ""

        params = {
            "domain": domain,
            "first_name": first_name,
            "last_name": last_name,
            "api_key": settings.hunter_api_key,
        }

        url = f"{HUNTER_FINDER_URL}?{urlencode(params)}"
        request = Request(url, headers={"Accept": "application/json"})

        try:
            with urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))

            email_data = data.get("data", {})
            email = email_data.get("email", "")
            confidence = email_data.get("confidence", 0)

            if email and confidence >= 50:
                self._daily_count += 1
                logger.info("Found email for {} at {}: {} (confidence: {})",
                            full_name, domain, email, confidence)
                return email

            logger.debug("Low confidence email for {} at {}: {} ({})",
                         full_name, domain, email, confidence)
            return None

        except HTTPError as exc:
            if exc.code == 429:
                logger.warning("Hunter.io rate limit reached")
            elif exc.code == 401:
                logger.warning("Hunter.io API key invalid")
            else:
                logger.debug("Hunter.io HTTP error: {}", exc.code)
            return None

    @staticmethod
    def _guess_domain(company: str) -> str:
        """Guess a company domain from its name."""
        if not company:
            return ""
        # Clean common suffixes
        cleaned = company.lower().strip()
        for suffix in (" inc", " llc", " ltd", " corp", " co", " company"):
            cleaned = cleaned.removesuffix(suffix)
        cleaned = cleaned.strip().replace(" ", "").replace(".", "")
        if not cleaned:
            return ""
        return f"{cleaned}.com"


# Singleton
email_finder = EmailFinder()
