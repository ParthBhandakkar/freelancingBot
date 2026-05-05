"""Native LinkedIn post search for real-time buyer-intent discovery.

Uses the logged-in browser session to search LinkedIn's native post search
filtered by "Past 24 Hours" to find people actively looking for freelance help.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote_plus

from loguru import logger

from browser.engine import BrowserEngine
from config import settings
from models.schemas import FreelanceClientLead, ProspectStatus
from utils.helpers import clean_text, human_delay
from utils.lead_intent import score_buyer_intent

POST_SEARCH_URL = (
    "https://www.linkedin.com/search/results/content/"
    "?keywords={keywords}&datePosted=%22past-24h%22&origin=FACETED_SEARCH&sortBy=%22date_posted%22"
)

POST_CARD_SELECTORS = [
    "div.feed-shared-update-v2",
    "div[data-urn*='activity']",
    "div.update-components-text",
]

AUTHOR_NAME_SELECTORS = [
    "span.update-components-actor__name span[aria-hidden='true']",
    "span.feed-shared-actor__name span[aria-hidden='true']",
    "a.update-components-actor__meta-link span[dir='ltr'] span[aria-hidden='true']",
    "a.app-aware-link span[dir='ltr']",
]

AUTHOR_HEADLINE_SELECTORS = [
    "span.update-components-actor__description span[aria-hidden='true']",
    "span.feed-shared-actor__description span[aria-hidden='true']",
]

AUTHOR_LINK_SELECTORS = [
    "a.update-components-actor__meta-link",
    "a.app-aware-link[href*='/in/']",
    "a.feed-shared-actor__container-link",
]

POST_TEXT_SELECTORS = [
    "div.feed-shared-update-v2__description-wrapper span[dir='ltr']",
    "span.break-words span[dir='ltr']",
    "div.update-components-text span[dir='ltr']",
    "div.feed-shared-text span[dir='ltr']",
]

POST_LINK_SELECTORS = [
    "a[href*='/feed/update/']",
    "a.update-components-actor__meta-link",
    "a[data-tracking-control-name*='update']",
]


class LinkedInPostSearcher:
    """Discover buyer-intent leads from LinkedIn's native post search."""

    def __init__(self, browser: BrowserEngine | None) -> None:
        self.browser = browser
        self.seen_posts: set[str] = set()

    def _browser_available(self) -> bool:
        return bool(
            self.browser is not None
            and BrowserEngine.is_available()
            and getattr(self.browser, "is_started", False)
        )

    async def discover_posts(
        self,
        max_results: int | None = None,
        queries: list[str] | None = None,
    ) -> list[FreelanceClientLead]:
        """Search LinkedIn posts natively for real-time buyer intent."""
        if not self._browser_available():
            logger.warning("Browser not available for native LinkedIn post search.")
            return []

        max_results = max_results or settings.max_discovery_results
        queries = queries or settings.linkedin_post_query_list
        leads: list[FreelanceClientLead] = []

        for query in queries:
            if len(leads) >= max_results:
                break

            remaining = max_results - len(leads)
            query_leads = await self._search_posts_for_query(query, remaining)
            leads.extend(query_leads)

            if len(leads) < max_results:
                await human_delay(settings.search_delay_min, settings.search_delay_max)

        # Dedupe and sort
        unique: list[FreelanceClientLead] = []
        seen: set[str] = set()
        for lead in leads:
            key = (lead.post_link or lead.profile_url or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(lead)

        unique.sort(key=lambda lead: lead.fit_score, reverse=True)
        return unique[:max_results]

    async def _search_posts_for_query(
        self, query: str, limit: int
    ) -> list[FreelanceClientLead]:
        url = POST_SEARCH_URL.format(keywords=quote_plus(query))
        logger.info("Searching LinkedIn posts natively for: {}", query)

        try:
            await self.browser.goto(url)  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("Failed to open LinkedIn post search: {}", exc)
            return []

        await human_delay(settings.search_delay_min, settings.search_delay_max)

        leads: list[FreelanceClientLead] = []

        for scroll_round in range(min(settings.scroll_rounds_per_query, 5)):
            extracted = await self._extract_posts_from_page(query)
            for lead in extracted:
                post_key = (lead.post_link or lead.profile_url or "").lower()
                if post_key in self.seen_posts:
                    continue
                self.seen_posts.add(post_key)
                leads.append(lead)
                if len(leads) >= limit:
                    return leads

            if len(leads) >= limit:
                break

            # Scroll down for more results
            try:
                await self.browser.page.mouse.wheel(0, 2000)  # type: ignore[union-attr]
            except Exception:
                pass
            await human_delay(settings.search_delay_min, settings.search_delay_max)

        return leads

    async def _extract_posts_from_page(
        self, query: str
    ) -> list[FreelanceClientLead]:
        """Extract post cards from the current LinkedIn search results page."""
        extracted: list[FreelanceClientLead] = []

        # Try to get all post update containers
        for card_selector in POST_CARD_SELECTORS:
            cards = self.browser.page.locator(card_selector)  # type: ignore[union-attr]
            count = await cards.count()
            if count == 0:
                continue

            for idx in range(min(count, 20)):
                card = cards.nth(idx)
                lead = await self._extract_lead_from_post_card(card, query)
                if lead is not None:
                    extracted.append(lead)

            if extracted:
                break

        # Fallback: try to extract from page text if no structured cards found
        if not extracted:
            extracted = await self._extract_from_page_text(query)

        return extracted

    async def _extract_lead_from_post_card(
        self, card, query: str
    ) -> FreelanceClientLead | None:
        """Extract a lead from a single LinkedIn post card."""
        try:
            # Get author name
            author_name = ""
            for selector in AUTHOR_NAME_SELECTORS:
                try:
                    locator = card.locator(selector).first
                    if await locator.count() > 0:
                        author_name = clean_text(await locator.inner_text())
                        if author_name:
                            break
                except Exception:
                    continue

            # Get author headline
            author_headline = ""
            for selector in AUTHOR_HEADLINE_SELECTORS:
                try:
                    locator = card.locator(selector).first
                    if await locator.count() > 0:
                        author_headline = clean_text(await locator.inner_text())
                        if author_headline:
                            break
                except Exception:
                    continue

            # Get author profile URL
            author_url = ""
            for selector in AUTHOR_LINK_SELECTORS:
                try:
                    locator = card.locator(selector).first
                    if await locator.count() > 0:
                        href = await locator.get_attribute("href") or ""
                        if "/in/" in href:
                            author_url = clean_text(href.split("?")[0])
                            break
                except Exception:
                    continue

            # Get post text
            post_text = ""
            for selector in POST_TEXT_SELECTORS:
                try:
                    locator = card.locator(selector).first
                    if await locator.count() > 0:
                        post_text = clean_text(await locator.inner_text())
                        if post_text and len(post_text) > 20:
                            break
                except Exception:
                    continue

            if not post_text:
                try:
                    post_text = clean_text(await card.inner_text())
                except Exception:
                    return None

            # Get post link
            post_link = ""
            for selector in POST_LINK_SELECTORS:
                try:
                    locator = card.locator(selector).first
                    if await locator.count() > 0:
                        href = await locator.get_attribute("href") or ""
                        if "/feed/update/" in href or "/posts/" in href:
                            post_link = clean_text(href.split("?")[0])
                            break
                except Exception:
                    continue

            if not author_name and not post_text:
                return None

            # Score buyer intent on the post text
            intent = score_buyer_intent(
                author_name, author_headline, post_text, query
            )

            # Only keep posts with active buyer intent
            if not intent.is_active_request:
                return None

            score = intent.score_boost + 55  # Base boost for native real-time post
            score = max(0, min(100, score))

            # Extract company from headline
            company = self._extract_company(author_headline)

            names = (author_name or "Unknown").split(" ", maxsplit=1)
            first_name = names[0] if names else ""
            last_name = names[1] if len(names) > 1 else ""

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            return FreelanceClientLead(
                lead_id=f"{post_link or author_url}::{query}",
                full_name=author_name or "Unknown",
                first_name=first_name,
                last_name=last_name,
                headline=clean_text(author_headline),
                company=company,
                location="",
                profile_url=author_url or post_link,
                post_link=post_link,
                profile_snippet=clean_text(post_text[:500]),
                matched_query=clean_text(query),
                source_platform="LinkedIn_Posts_Native",
                source_query=clean_text(query),
                fit_score=score,
                match_tags=";".join(intent.tags[:6]),
                status=ProspectStatus.CANDIDATE,
                discovered_at=now,
                notes=intent.reason or "Real-time LinkedIn post with active buyer intent.",
            )

        except Exception as exc:
            logger.debug("Failed to extract post card: {}", str(exc)[:200])
            return None

    async def _extract_from_page_text(
        self, query: str
    ) -> list[FreelanceClientLead]:
        """Fallback: extract leads from raw page text."""
        try:
            page_text = await self.browser.get_page_text()  # type: ignore[union-attr]
        except Exception:
            return []

        if not page_text or len(page_text) < 100:
            return []

        intent = score_buyer_intent(page_text, query)
        if not intent.is_active_request:
            return []

        logger.debug("Page text fallback found buyer intent for query: {}", query)
        return []

    @staticmethod
    def _extract_company(headline: str) -> str:
        """Extract company name from a headline like 'CEO at AcmeCorp'."""
        patterns = (
            r"@\s*([^|,]+)",
            r"\bat\s+([^|,]+)",
            r"\|\s*([^|,]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, headline, flags=re.IGNORECASE)
            if match:
                return clean_text(match.group(1))
        return ""
