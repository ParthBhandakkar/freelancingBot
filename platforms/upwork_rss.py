"""Upwork RSS feed discovery for real-time job leads.

Parses Upwork's public RSS feeds sorted by recency to find fresh job postings.
No browser or authentication required.
"""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import quote_plus
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from loguru import logger

from config import settings
from models.schemas import FreelanceClientLead, ProspectStatus
from utils.helpers import clean_text
from utils.lead_intent import score_buyer_intent

UPWORK_RSS_URL = (
    "https://www.upwork.com/ab/feed/jobs/rss"
    "?q={query}&sort=recency&paging=0%3B20"
)

UPWORK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml",
}

HTML_TAG_RE = re.compile(r"<[^>]+>")
BUDGET_RE = re.compile(r"(?:Budget|Fixed[- ]Price|Hourly Range):\s*([^\n<]+)", re.IGNORECASE)
SKILLS_RE = re.compile(r"Skills?:\s*([^\n<]+)", re.IGNORECASE)


class UpworkRSSDiscovery:
    """Discover fresh Upwork job postings via RSS feeds."""

    def __init__(self) -> None:
        self.seen_urls: set[str] = set()

    async def discover(
        self,
        max_results: int | None = None,
        queries: list[str] | None = None,
    ) -> list[FreelanceClientLead]:
        max_results = max_results or settings.max_discovery_results
        queries = queries or settings.upwork_rss_query_list
        leads: list[FreelanceClientLead] = []

        for query in queries:
            if len(leads) >= max_results:
                break
            remaining = max_results - len(leads)
            try:
                query_leads = await asyncio.to_thread(self._fetch_and_parse, query, remaining)
                leads.extend(query_leads)
            except Exception as exc:
                logger.warning("Upwork RSS failed for '{}': {}", query, exc)

        unique: list[FreelanceClientLead] = []
        seen: set[str] = set()
        for lead in leads:
            key = lead.profile_url.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(lead)
        unique.sort(key=lambda lead: lead.fit_score, reverse=True)
        return unique[:max_results]

    def _fetch_and_parse(self, query: str, limit: int) -> list[FreelanceClientLead]:
        url = UPWORK_RSS_URL.format(query=quote_plus(query))
        logger.info("Fetching Upwork RSS for: {}", query)
        xml_text = self._fetch_rss(url)
        if not xml_text:
            return []
        return self._parse_feed(xml_text, query, limit)

    def _fetch_rss(self, url: str) -> str:
        for attempt in range(1, 4):
            request = Request(url, headers=UPWORK_HEADERS)
            try:
                with urlopen(request, timeout=20) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except HTTPError as exc:
                if exc.code == 429 and attempt < 3:
                    import time
                    time.sleep(2.0 * attempt)
                    continue
                logger.warning("Upwork RSS HTTP error {}: {}", exc.code, exc)
                return ""
            except Exception as exc:
                logger.warning("Upwork RSS fetch error: {}", exc)
                return ""
        return ""

    def _parse_feed(self, xml_text: str, query: str, limit: int) -> list[FreelanceClientLead]:
        leads: list[FreelanceClientLead] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("Upwork RSS XML parse error: {}", exc)
            return []

        channel = root.find("channel")
        items = channel.findall("item") if channel is not None else root.findall("item")
        logger.info("Upwork RSS returned {} items for '{}'", len(items), query)

        for item in items:
            if len(leads) >= limit:
                break
            lead = self._parse_item(item, query)
            if lead is None:
                continue
            url_key = lead.profile_url.lower()
            if url_key in self.seen_urls:
                continue
            self.seen_urls.add(url_key)
            leads.append(lead)
        return leads

    def _parse_item(self, item: ET.Element, query: str) -> FreelanceClientLead | None:
        title = self._el_text(item, "title")
        link = self._el_text(item, "link") or self._el_text(item, "guid")
        description = self._el_text(item, "description")
        if not link:
            return None

        clean_desc = clean_text(HTML_TAG_RE.sub(" ", description or ""))
        clean_title = clean_text(title or "")
        if not clean_title and not clean_desc:
            return None

        budget = self._re_match(BUDGET_RE, clean_desc)
        combined = f"{clean_title} {clean_desc}".lower()
        intent = score_buyer_intent(clean_title, clean_desc, query)

        score = 45 + intent.score_boost
        tags = ["upwork_rss", "job_post"] + intent.tags[:4]
        if budget:
            score += 10
            tags.append("has_budget")

        industry_hits = [i for i in settings.industry_keyword_list if i and i in combined]
        score += len(industry_hits) * 4
        score = max(0, min(100, score))

        status = ProspectStatus.CANDIDATE if score >= settings.min_fit_score else ProspectStatus.DISCOVERED
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snippet = clean_text(f"{clean_title}. {clean_desc[:300]}")
        if budget:
            snippet = f"Budget: {budget}. {snippet}"

        return FreelanceClientLead(
            lead_id=f"{link}::{query}",
            full_name=clean_title[:120],
            headline=clean_title,
            company="Upwork Job",
            profile_url=clean_text(link),
            post_link=clean_text(link),
            profile_snippet=snippet[:500],
            matched_query=clean_text(query),
            source_platform="Upwork_RSS",
            source_query=clean_text(query),
            fit_score=score,
            match_tags=";".join(dict.fromkeys(tags)),
            status=status,
            discovered_at=now,
            notes=f"Real-time Upwork RSS. {budget or ''}".strip(),
        )

    @staticmethod
    def _el_text(element: ET.Element, tag: str) -> str:
        child = element.find(tag)
        return child.text.strip() if child is not None and child.text else ""

    @staticmethod
    def _re_match(pattern: re.Pattern, text: str) -> str:
        match = pattern.search(text)
        return clean_text(match.group(1)) if match else ""
