"""LinkedIn prospect search for potential freelance clients."""
from __future__ import annotations

import asyncio
import html as html_lib
import json
import re
import time
from datetime import datetime
from urllib.parse import quote_plus, unquote, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from loguru import logger

from browser.engine import BrowserEngine
from config import settings
from llm.client import llm_client
from llm.prompts import CLIENT_FIT_SYSTEM, CLIENT_FIT_USER
from models.schemas import FreelanceClientLead, ProspectStatus
from utils.helpers import clean_text, human_delay
from utils.lead_intent import score_buyer_intent

PEOPLE_SEARCH_URL = (
    "https://www.linkedin.com/search/results/people/?"
    "keywords={keywords}&origin=GLOBAL_SEARCH_HEADER"
)
BRAVE_SEARCH_URL = "https://search.brave.com/search?q={query}&source=web"
PUBLIC_RESULT_PATTERN = re.compile(
    r'title:"([^"]+)",\s*url:"(https?://(?:[\w-]+\.)?linkedin\.com/in/[^"]+)",[\s\S]*?description:"([^"]*)"',
    re.IGNORECASE | re.S,
)

NAME_SELECTORS = [
    "span[aria-hidden='true'].t-14.t-black.t-bold",
    "span[aria-hidden='true'].entity-result__title-text",
    "a[href*='/in/'] .entity-result__title-text",
    "a[href*='/in/'] span",
]
HEADLINE_SELECTORS = [
    "div.entity-result__primary-subtitle",
    ".entity-result__summary",
    ".search-result__snippets",
]
COMPANY_SELECTORS = [
    "p.entity-result__secondary-subtitle",
    "p.search-result__truncate",
]
LOCATION_SELECTORS = [
    "p.entity-result__secondary-subtitle",
    "p.search-result__secondary-subtitle",
]

PERSON_CARD_SELECTORS = [
    "li.reusable-search__result-container",
    "div.search-result__wrapper",
    "li[data-chameleon-result-urn]",
]

PROFILE_NAME_SELECTORS = [
    "h1",
    ".text-heading-xlarge",
    ".pv-text-details__left-panel h1",
]


class LinkedInClientSearcher:
    def __init__(self, browser: BrowserEngine | None):
        self.browser = browser
        self.seen_profiles: set[str] = set()

    async def discover_clients(self, max_results: int | None = None) -> list[FreelanceClientLead]:
        max_results = max_results or settings.max_discovery_results
        leads: list[FreelanceClientLead] = []
        use_browser_search = self._browser_search_available()

        for query in settings.all_search_query_list:
            if len(leads) >= max_results:
                break

            remaining = max_results - len(leads)
            query_leads: list[FreelanceClientLead] = []

            if use_browser_search:
                query_leads.extend(await self._discover_by_query(query, remaining))
                await self._enrich_missing_names(query_leads)

            if len(query_leads) < remaining:
                existing = {lead.profile_url.lower() for lead in query_leads}
                public_leads = await self._discover_public_by_query(query, remaining)
                query_leads.extend(
                    [lead for lead in public_leads if lead.profile_url.lower() not in existing]
                )

            leads.extend(query_leads[:remaining])

            if len(leads) >= max_results:
                break

            if use_browser_search:
                await human_delay(settings.search_delay_min, settings.search_delay_max)

        unique: list[FreelanceClientLead] = []
        seen = set()
        for lead in leads:
            key = lead.profile_url.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(lead)

        unique.sort(key=lambda lead: lead.fit_score, reverse=True)
        return unique[:max_results]

    async def _discover_by_query(self, query: str, limit: int) -> list[FreelanceClientLead]:
        query_results: list[FreelanceClientLead] = []
        if not self._browser_search_available():
            return query_results

        url = PEOPLE_SEARCH_URL.format(keywords=quote_plus(query))

        logger.info("Searching LinkedIn clients for query: {}", query)
        try:
            await self.browser.goto(url)  # type: ignore[union-attr]
        except Exception as exc:
            logger.error("Failed to open people search: {}", exc)
            return query_results

        await human_delay(settings.search_delay_min, settings.search_delay_max)

        for _ in range(settings.scroll_rounds_per_query):
            cards = await self._extract_cards_from_page(query)
            for lead in cards:
                if len(query_results) >= limit:
                    return query_results

                if lead.profile_url in self.seen_profiles:
                    continue
                if self._is_blacklisted(lead):
                    continue

                self.seen_profiles.add(lead.profile_url)
                query_results.append(lead)

            if len(query_results) >= limit:
                break

            await self.browser.page.mouse.wheel(0, 1500)  # type: ignore[union-attr]
            await self._scroll_wait()

            if limit <= 0:
                break

        return query_results

    async def _discover_public_by_query(self, query: str, limit: int) -> list[FreelanceClientLead]:
        if limit <= 0:
            return []

        public_query = clean_text(f"site:linkedin.com/in {query}")
        public_url = BRAVE_SEARCH_URL.format(query=quote_plus(public_query))
        logger.info("Searching public LinkedIn results for query: {}", query)

        try:
            page_html = await asyncio.to_thread(self._fetch_public_search_html, public_url)
        except Exception as exc:
            logger.warning("Public LinkedIn search failed for '{}': {}", query, exc)
            return []

        leads: list[FreelanceClientLead] = []
        for raw_title, raw_url, raw_description in PUBLIC_RESULT_PATTERN.findall(page_html):
            profile_url = clean_text(self._decode_search_string(raw_url))
            if not profile_url or "/in/" not in profile_url:
                continue
            if profile_url in self.seen_profiles:
                continue

            title = self._decode_search_string(raw_title)
            description = self._decode_search_string(raw_description)
            lead = self._build_public_lead(
                profile_url=profile_url,
                title=title,
                description=description,
                query=query,
            )
            if lead is None or self._is_blacklisted(lead):
                continue

            self.seen_profiles.add(profile_url)
            leads.append(lead)
            if len(leads) >= limit:
                break

        return leads

    async def _scroll_wait(self) -> None:
        await human_delay(settings.search_delay_min, settings.search_delay_max)

    async def _extract_cards_from_page(self, matched_query: str) -> list[FreelanceClientLead]:
        extracted: list[FreelanceClientLead] = []
        selector_group = ", ".join(PERSON_CARD_SELECTORS)
        cards = self.browser.page.locator(selector_group)  # type: ignore[union-attr]
        count = await cards.count()
        if count == 0:
            return await self._extract_from_links(matched_query)

        for idx in range(min(count, 24)):
            card = cards.nth(idx)
            lead = await self._extract_lead_from_card(card, matched_query)
            if lead is None:
                continue
            extracted.append(lead)

        return extracted

    async def _extract_from_links(self, matched_query: str) -> list[FreelanceClientLead]:
        extracted: list[FreelanceClientLead] = []
        links = self.browser.page.locator("a[href*='/in/']")  # type: ignore[union-attr]
        count = await links.count()
        for idx in range(min(count, 24)):
            link = links.nth(idx)
            try:
                href = await link.get_attribute("href") or ""
                href = clean_text(href)
                if not href or "/in/" not in href:
                    continue
                lead = await self._build_lead_from_text(
                    href,
                    matched_query,
                    lead_text=clean_text(await link.inner_text()),
                )
                if lead:
                    extracted.append(lead)
            except Exception:
                continue
        return extracted

    async def _extract_lead_from_card(self, card, matched_query: str) -> FreelanceClientLead | None:
        link = card.locator("a[href*='/in/']").first
        profile_url = await link.get_attribute("href") or ""
        profile_url = clean_text(profile_url)

        if not profile_url or "/in/" not in profile_url:
            return None

        raw_text = clean_text(await card.inner_text())
        name = clean_text(await self._read_locator_text(card, NAME_SELECTORS))
        headline = clean_text(await self._read_locator_text(card, HEADLINE_SELECTORS))
        company = clean_text(await self._read_locator_text(card, COMPANY_SELECTORS))
        location = clean_text(await self._read_locator_text(card, LOCATION_SELECTORS))

        if not name:
            name = self._extract_name_from_text(raw_text, profile_url=profile_url)

        return self._build_lead(
            profile_url=profile_url,
            full_name=name,
            headline=headline,
            company=company,
            location=location,
            snippet=raw_text,
            query=matched_query,
        )

    async def _build_lead_from_text(
        self,
        profile_url: str,
        matched_query: str,
        lead_text: str,
    ) -> FreelanceClientLead | None:
        if not lead_text:
            return None
        name = self._extract_name_from_text(lead_text, profile_url=profile_url)
        return self._build_lead(
            profile_url=profile_url,
            full_name=name,
            headline=lead_text,
            company="",
            location="",
            snippet=lead_text,
            query=matched_query,
        )

    def _build_public_lead(
        self,
        *,
        profile_url: str,
        title: str,
        description: str,
        query: str,
    ) -> FreelanceClientLead | None:
        cleaned_title = clean_text(title).removesuffix("| LinkedIn").strip(" -|")
        cleaned_description = clean_text(description)
        if not cleaned_title:
            return None

        name, headline = self._split_public_title(cleaned_title)
        location = self._extract_between(cleaned_description, "Location:", "·")
        company = self._extract_between(cleaned_description, "Experience:", "·")
        if not company:
            company = self._extract_company_from_headline(headline)

        return self._build_lead(
            profile_url=profile_url,
            full_name=name or cleaned_title,
            headline=headline or cleaned_title,
            company=company,
            location=location,
            snippet=clean_text(f"{cleaned_title} {cleaned_description}"),
            query=query,
        )

    def _build_lead(
        self,
        *,
        profile_url: str,
        full_name: str,
        headline: str,
        company: str,
        location: str,
        snippet: str,
        query: str,
    ) -> FreelanceClientLead:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        normalized_name = clean_text(full_name)
        if self._needs_name_enrichment(normalized_name):
            normalized_name = self._extract_name_from_profile_url(profile_url)
        names = normalized_name.split(" ", maxsplit=1)
        first_name = names[0] if names else ""
        last_name = names[1] if len(names) > 1 else ""

        score, tags, is_candidate = self._rule_based_score(
            full_name=normalized_name,
            headline=headline,
            company=company,
            location=location,
            snippet=snippet,
            query=query,
        )

        final_score = max(0, min(100, score))
        fit_reason = " ".join(tags)

        if final_score >= settings.min_fit_score:
            status = ProspectStatus.CANDIDATE if is_candidate else ProspectStatus.DISCOVERED
        else:
            status = ProspectStatus.DISCOVERED

        return FreelanceClientLead(
            lead_id=f"{profile_url}::{query}",
            full_name=normalized_name,
            first_name=first_name,
            last_name=last_name,
            headline=clean_text(headline),
            company=clean_text(company),
            location=clean_text(location),
            profile_url=clean_text(profile_url),
            profile_snippet=clean_text(snippet),
            matched_query=clean_text(query),
            source_platform="LinkedIn",
            source_query=clean_text(query),
            fit_score=final_score,
            match_tags=";".join(tags),
            status=status,
            discovered_at=now,
            notes=fit_reason,
        )

    async def score_with_llm(self, lead: FreelanceClientLead) -> FreelanceClientLead:
        if not settings.has_llm_key:
            return lead

        intent = score_buyer_intent(
            lead.full_name,
            lead.headline,
            lead.company,
            lead.location,
            lead.profile_snippet,
            lead.matched_query,
        )
        rule_score = lead.fit_score

        payload = CLIENT_FIT_USER.format(
            freelancer_focus=settings.freelancer_focus,
            portfolio_url=settings.portfolio_url,
            role_keywords=", ".join(settings.role_keyword_list),
            full_name=lead.full_name,
            headline=lead.headline,
            company=lead.company,
            location=lead.location,
            query=lead.matched_query,
            snippet=lead.profile_snippet,
        )

        try:
            response = await llm_client.chat_json(
                system_prompt=CLIENT_FIT_SYSTEM,
                user_message=payload,
                max_tokens=800,
                temperature=0.2,
            )
            if isinstance(response, dict):
                lead.fit_score = max(
                    0,
                    min(100, int(response.get("fit_score", lead.fit_score))),
                )
                if intent.is_active_request:
                    lead.fit_score = max(lead.fit_score, rule_score, settings.min_fit_score + 25)
                lead.notes = str(response.get("match_reason", lead.notes)).strip()
                if intent.reason:
                    lead.notes = clean_text(f"{intent.reason} {lead.notes}")
                tags = response.get("target_fit_tags") or []
                if isinstance(tags, list):
                    merged_tags = [str(tag) for tag in tags] + intent.tags
                    lead.match_tags = ";".join(list(dict.fromkeys(merged_tags))[:8])

                if (
                    lead.fit_score >= settings.min_fit_score
                    and (response.get("is_candidate") is True or intent.is_active_request)
                ):
                    lead.status = ProspectStatus.CANDIDATE
            return lead
        except Exception:
            logger.debug("LLM lead fitting failed; using rule score")
        return lead

    async def _enrich_missing_names(self, leads: list[FreelanceClientLead]) -> None:
        if not self._browser_search_available():
            return

        for lead in leads:
            if not self._needs_name_enrichment(lead.full_name):
                continue
            enriched_name = await self._fetch_profile_name(lead.profile_url)
            if not enriched_name:
                enriched_name = self._extract_name_from_profile_url(lead.profile_url)
            if not enriched_name or self._needs_name_enrichment(enriched_name):
                continue

            lead.full_name = enriched_name
            names = enriched_name.split(" ", maxsplit=1)
            lead.first_name = names[0] if names else ""
            lead.last_name = names[1] if len(names) > 1 else ""

    async def _fetch_profile_name(self, profile_url: str) -> str:
        if not profile_url or not self._browser_search_available():
            return ""

        current_url = ""
        try:
            current_url = await self.browser.get_current_url()  # type: ignore[union-attr]
        except Exception:
            current_url = ""

        try:
            await self.browser.goto(profile_url, wait_until="domcontentloaded")  # type: ignore[union-attr]
            await human_delay(1.0, 1.8)
            for selector in PROFILE_NAME_SELECTORS:
                text = clean_text(await self.browser.page.locator(selector).first.inner_text())  # type: ignore[union-attr]
                if text and not self._needs_name_enrichment(text):
                    return text
        except Exception:
            return ""
        finally:
            if current_url:
                try:
                    await self.browser.goto(current_url, wait_until="domcontentloaded")  # type: ignore[union-attr]
                    await human_delay(0.6, 1.0)
                except Exception:
                    pass
        return ""

    def _rule_based_score(
        self,
        *,
        full_name: str,
        headline: str,
        company: str,
        location: str,
        snippet: str,
        query: str,
    ) -> tuple[int, list[str], bool]:
        text = " ".join([full_name, headline, company, location, snippet, query]).lower()
        score = 0
        matched_tags: list[str] = []

        role_hits = [r for r in settings.role_keyword_list if r and r in text]
        industry_hits = [i for i in settings.industry_keyword_list if i and i in text]
        q_hits = [q for q in re.split(r"[\s,;-]", query.lower()) if q and len(q) > 2 and q in text]

        score += len(role_hits) * 12
        score += len(industry_hits) * 10
        score += len(q_hits) * 6

        if full_name:
            score += 5

        blacklist = [w for w in settings.lead_blacklist_list if w and w in text]
        if blacklist:
            score -= len(blacklist) * 25

        buyer_intent = score_buyer_intent(full_name, headline, company, location, snippet, query)
        score += buyer_intent.score_boost

        matched_tags.extend(role_hits)
        matched_tags.extend(industry_hits)
        matched_tags.extend(buyer_intent.tags)
        if not matched_tags:
            matched_tags.append("needs_review")

        is_candidate = score >= settings.min_fit_score or buyer_intent.is_active_request
        return score, matched_tags, is_candidate

    def _is_blacklisted(self, lead: FreelanceClientLead) -> bool:
        text = " ".join([lead.full_name, lead.headline, lead.company]).lower()
        return any(black in text for black in settings.lead_blacklist_list)

    def _browser_search_available(self) -> bool:
        return bool(
            self.browser is not None
            and BrowserEngine.is_available()
            and getattr(self.browser, "is_started", False)
        )

    async def _read_locator_text(self, scope, selectors: list[str]) -> str:
        for selector in selectors:
            try:
                locator = scope.locator(selector).first
                if await locator.count() == 0:
                    continue
                text = await locator.inner_text()
                value = clean_text(text)
                if value:
                    return value
            except Exception:
                continue
        return ""

    @staticmethod
    def _extract_name_from_text(text: str, profile_url: str = "") -> str:
        if not text:
            return LinkedInClientSearcher._extract_name_from_profile_url(profile_url)
        parts = re.split(r"[\n\r]+", text)
        for part in parts:
            candidate = clean_text(part)
            if candidate and len(candidate) < 120 and not LinkedInClientSearcher._looks_like_non_name(candidate):
                return candidate
        return LinkedInClientSearcher._extract_name_from_profile_url(profile_url)

    @staticmethod
    def _extract_name_from_profile_url(profile_url: str) -> str:
        parsed = urlparse(profile_url or "")
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            return "Unknown"
        slug = unquote(parts[-1])
        slug = re.sub(r"[-_]+", " ", slug)
        slug = re.sub(r"\d+", " ", slug)
        slug = clean_text(slug.title())
        return slug or "Unknown"

    @staticmethod
    def _looks_like_non_name(value: str) -> bool:
        lowered = (value or "").strip().lower()
        if not lowered:
            return True
        banned_tokens = ("linkedin", "message", "connect", "follow", "open to work")
        return any(token in lowered for token in banned_tokens)

    @staticmethod
    def _needs_name_enrichment(name: str) -> bool:
        cleaned = clean_text(name)
        if not cleaned:
            return True
        lowered = cleaned.lower()
        return lowered in {"unknown", "linkedin member"} or LinkedInClientSearcher._looks_like_non_name(cleaned)

    @staticmethod
    def _fetch_public_search_html(url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        for attempt in range(1, 4):
            request = Request(url, headers=headers)
            try:
                with urlopen(request, timeout=20) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except HTTPError as exc:
                if exc.code != 429 or attempt == 3:
                    raise
                time.sleep(1.5 * attempt)

        raise RuntimeError(f"Unable to fetch public search results from {url}")

    @staticmethod
    def _decode_search_string(raw: str) -> str:
        if not raw:
            return ""
        try:
            value = json.loads(f'"{raw}"')
        except Exception:
            value = raw
        return clean_text(html_lib.unescape(str(value)))

    @staticmethod
    def _split_public_title(title: str) -> tuple[str, str]:
        pieces = [piece.strip() for piece in title.split(" - ", maxsplit=1)]
        if len(pieces) == 2:
            return pieces[0], pieces[1]
        return title, title

    @staticmethod
    def _extract_between(text: str, start_marker: str, end_marker: str) -> str:
        if start_marker not in text:
            return ""
        tail = text.split(start_marker, maxsplit=1)[1]
        if end_marker in tail:
            tail = tail.split(end_marker, maxsplit=1)[0]
        return clean_text(tail)

    @staticmethod
    def _extract_company_from_headline(headline: str) -> str:
        patterns = (
            r"@\s*([^|,]+)",
            r"\bat\s+([^|,]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, headline, flags=re.IGNORECASE)
            if match:
                return clean_text(match.group(1))
        return ""
