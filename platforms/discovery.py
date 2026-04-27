"""Cross-platform discovery for client leads."""
from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from loguru import logger

from browser.engine import BrowserEngine
from config import settings
from models.schemas import FreelanceClientLead, ProspectStatus
from utils.helpers import clean_text, human_delay
from utils.lead_intent import score_buyer_intent


@dataclass(frozen=True)
class PlatformDefinition:
    name: str
    site: str
    search_template: str
    profile_filters: tuple[str, ...]


PLATFORM_DEFINITIONS: tuple[PlatformDefinition, ...] = (
    PlatformDefinition(
        name="LinkedIn_Posts",
        site="linkedin.com",
        search_template="https://duckduckgo.com/html/?q={query}",
        profile_filters=("/posts/", "/feed/update/", "/pulse/"),
    ),
    PlatformDefinition(
        name="Upwork",
        site="upwork.com",
        search_template="https://duckduckgo.com/html/?q={query}",
        profile_filters=(
            "/services/",
            "/freelancers/",
            "/o/freelancers/",
            "/hire/",
            "/freelance-jobs/",
            "/jobs/",
        ),
    ),
    PlatformDefinition(
        name="Fiverr",
        site="fiverr.com",
        search_template="https://duckduckgo.com/html/?q={query}",
        profile_filters=("/users/", "/seller/"),
    ),
    PlatformDefinition(
        name="Clutch",
        site="clutch.co",
        search_template="https://duckduckgo.com/html/?q={query}",
        profile_filters=("/profile/", "/profiles/", "/company-profile/"),
    ),
)

BUYER_SIGNAL_TERMS = (
    "hiring",
    "hire",
    "looking for",
    "looking to hire",
    "need help",
    "need a",
    "project",
    "contract",
    "job post",
    "job listing",
)

COMPANY_SIGNAL_TERMS = (
    "inc",
    "llc",
    "ltd",
    "company",
    "startup",
    "founder",
    "ceo",
    "cto",
)

DIRECTORY_SIGNAL_TERMS = (
    "top companies",
    "best companies",
    "directory",
    "company listings",
    "agencies",
    "agency list",
    "firms",
)


def _normalise_search_href(href: str) -> str:
    if not href:
        return ""

    if "/l/?uddg=" in href:
        parsed = urlparse(href)
        query = parse_qs(parsed.query or "")
        encoded = query.get("uddg", [None])[0]
        if encoded:
            return unquote(encoded)

    if href.startswith("//"):
        href = f"https:{href}"
    return href


def _url_profile_name(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return url
    candidate = parts[-1].replace("-", " ").replace("_", " ")
    return clean_text(candidate.title())


class PlatformDiscoveryService:
    """Discover client leads from search engines for platforms beyond LinkedIn."""

    def __init__(self, browser: BrowserEngine) -> None:
        self.browser = browser

    async def discover(
        self,
        max_results: int | None = None,
        platform_sources: list[str] | None = None,
    ) -> list[FreelanceClientLead]:
        max_results = max_results or settings.max_discovery_results
        if not settings.discover_platform_list:
            return []

        discovered: list[FreelanceClientLead] = []
        sources = self._active_sources(platform_sources)
        if not sources:
            return []

        for query in settings.all_search_query_list:
            if len(discovered) >= max_results:
                break

            per_query_limit = min(settings.max_web_results_per_query, max_results - len(discovered))
            if per_query_limit <= 0:
                break

            for source in sources:
                try:
                    discovered.extend(
                        await self._discover_from_source(
                            source=source,
                            query=query,
                            max_results=per_query_limit,
                        )
                    )
                except Exception as exc:
                    logger.warning("Platform discovery failed for {} / {}: {}", source.name, query, exc)

                if len(discovered) >= max_results:
                    break

            await human_delay(settings.search_delay_min, settings.search_delay_max)

        if not discovered and max_results > 0:
            generic_query = f'"need help" "{settings.freelancer_focus}" freelancer project'
            for source in sources:
                if len(discovered) >= max_results:
                    break
                try:
                    discovered.extend(
                        await self._discover_from_source(
                            source=source,
                            query=generic_query,
                            max_results=max_results - len(discovered),
                            allow_fallback=True,
                        )
                    )
                except Exception as exc:
                    logger.warning("Fallback platform discovery failed for {}: {}", source.name, exc)

                if len(discovered) >= max_results:
                    break

        return discovered[:max_results]

    def _active_sources(self, platform_sources: list[str] | None = None) -> list[PlatformDefinition]:
        source_names = platform_sources or settings.discover_platform_list
        selected = {name.lower() for name in source_names}
        return [
            source
            for source in PLATFORM_DEFINITIONS
            if source.name.lower() in selected
        ]

    async def _discover_from_source(
        self,
        *,
        source: PlatformDefinition,
        query: str,
        max_results: int,
        allow_fallback: bool = False,
    ) -> list[FreelanceClientLead]:
        search_query = clean_text(f"{query} {settings.freelancer_focus} site:{source.site}")
        if not search_query:
            return []

        # Use Jina AI proxy for DuckDuckGo to avoid bot-facing anti-bot challenge pages.
        search_url = source.search_template.format(
            query=quote_plus(search_query)
        ).replace("duckduckgo.com/html/", "r.jina.ai/http://duckduckgo.com/html/")
        await self.browser.goto(search_url)
        await human_delay(settings.search_delay_min, settings.search_delay_max)

        page_html = await self.browser.evaluate("document.body.innerHTML")
        if isinstance(page_html, dict):
            page_html = page_html.get("result") or page_html.get("content") or ""
        elif not isinstance(page_html, str):
            return []
        page_html = str(page_html)
        if not page_html.strip():
            return []
        logger.debug("Raw search HTML size for {} '{}': {} chars", source.name, query, len(page_html))

        leads: list[FreelanceClientLead] = []
        seen_urls: set[str] = set()

        anchor_pattern = re.compile(
            r"<a[^>]+href=(?:\"|')([^\"']+)(?:\"|')[^>]*>(.*?)</a>",
            re.IGNORECASE | re.S,
        )
        markdown_link_pattern = re.compile(r"\[([^\]]+)\]\(([^()\s]+)\)")
        anchor_matches = list(anchor_pattern.finditer(page_html))
        markdown_matches = list(markdown_link_pattern.finditer(page_html))
        logger.info(
            "Found {} html anchors and {} markdown links for {} query '{}'",
            len(anchor_matches),
            len(markdown_matches),
            source.name,
            query,
        )

        for href_raw, title_raw in (
            [(m.group(1), m.group(2)) for m in anchor_matches]
            + [(m.group(2), m.group(1)) for m in markdown_matches]
        ):
            href = clean_text(_normalise_search_href(href_raw))
            if not href:
                continue
            if source.site not in href.lower():
                continue
            if not (any(fragment in href.lower() for fragment in source.profile_filters) or allow_fallback):
                continue
            if href in seen_urls:
                continue

            title = clean_text(html_lib.unescape(re.sub(r"<[^>]+>", " ", title_raw)))
            snippet = clean_text(_result_snippet(page_html, href))
            if not title and not snippet:
                continue
            if self._is_search_artifact(title, href):
                continue

            qualified = self._qualify_result(
                source=source,
                href=href,
                title=title,
                snippet=snippet,
                query=query,
            )
            if qualified is None:
                continue

            seen_urls.add(href)
            logger.debug("Accepted platform candidate {} -> {} ({})", source.name, title or _url_profile_name(href), href)

            leads.append(
                self._build_lead(
                    full_name=title or _url_profile_name(href),
                    headline=_url_profile_name(href) if not title else title,
                    company="",
                    location="",
                    snippet=snippet or clean_text(f"{title} {href}"),
                    query=query,
                    profile_url=href,
                    post_link=href,
                    source=source.name,
                    fit_score=qualified["fit_score"],
                    match_tags=qualified["match_tags"],
                    status=qualified["status"],
                    notes=qualified["notes"],
                )
            )

            if len(leads) >= max_results:
                break

        return leads

    @staticmethod
    def _build_lead(
        *,
        full_name: str,
        headline: str,
        company: str,
        location: str,
        snippet: str,
        query: str,
        profile_url: str,
        post_link: str = "",
        source: str,
        fit_score: int = 0,
        match_tags: str = "",
        status: ProspectStatus = ProspectStatus.DISCOVERED,
        notes: str = "",
    ) -> FreelanceClientLead:
        cleaned_name = clean_text(full_name)
        names = cleaned_name.split(" ", maxsplit=1)
        first_name = names[0] if names else ""
        last_name = names[1] if len(names) > 1 else ""

        return FreelanceClientLead(
            lead_id=f"{profile_url}::{query}",
            full_name=cleaned_name,
            first_name=first_name,
            last_name=last_name,
            headline=clean_text(headline),
            company=clean_text(company),
            location=clean_text(location),
            profile_url=clean_text(profile_url),
            post_link=clean_text(post_link),
            profile_snippet=clean_text(snippet),
            matched_query=clean_text(query),
            source_platform=source,
            source_query=clean_text(query),
            fit_score=max(0, min(100, fit_score)),
            match_tags=clean_text(match_tags),
            status=status,
            discovered_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            notes=clean_text(notes),
        )

    @staticmethod
    def _is_search_artifact(title: str, href: str) -> bool:
        title_lower = (title or "").lower()
        href_lower = (href or "").lower()
        if not href_lower or href_lower.endswith(".ico"):
            return True
        if "external-content.duckduckgo.com" in href_lower:
            return True
        if "![image" in title_lower or title_lower.startswith("[!"):
            return True
        return False

    def _qualify_result(
        self,
        *,
        source: PlatformDefinition,
        href: str,
        title: str,
        snippet: str,
        query: str,
    ) -> dict[str, object] | None:
        href_lower = href.lower()
        text = clean_text(" ".join([title, snippet, query])).lower()
        tags: list[str] = []
        score = 0

        buyer_intent = score_buyer_intent(title, snippet, query)

        if source.name == "LinkedIn_Posts":
            if not any(part in href_lower for part in ("/posts/", "/feed/update/", "/pulse/")):
                return None
            if not buyer_intent.is_active_request:
                return None
            score += 55
            tags.append("linkedin_buyer_post")
        elif source.name == "Upwork":
            if any(part in href_lower for part in ("/services/", "/freelancers/", "/o/freelancers/", "/hire/")):
                return None
            if any(part in href_lower for part in ("/jobs/", "/freelance-jobs/")):
                score += 40
                tags.append("job_post")
            else:
                return None
        elif source.name == "Fiverr":
            # Public search results are almost always seller listings rather than buyer-side opportunities.
            return None
        elif source.name == "Clutch":
            if "/profile/" in href_lower or "/company-profile/" in href_lower:
                score += 25
                tags.append("company_profile")
            else:
                return None

            if any(term in text for term in DIRECTORY_SIGNAL_TERMS):
                return None

        buyer_hits = [term for term in BUYER_SIGNAL_TERMS if term in text]
        company_hits = [term for term in COMPANY_SIGNAL_TERMS if term in text]
        if buyer_hits:
            score += 25
            tags.extend(buyer_hits[:2])
        if buyer_intent.score_boost:
            score += buyer_intent.score_boost
            tags.extend(buyer_intent.tags)
        if company_hits:
            score += 12
            tags.extend(company_hits[:2])

        if source.name == "Clutch" and "services & company info" in text:
            tags.append("company_context")

        if not tags:
            tags.append("needs_review")

        status = ProspectStatus.CANDIDATE if score >= settings.min_fit_score or buyer_intent.is_active_request else ProspectStatus.DISCOVERED
        reason = (
            buyer_intent.reason or "External lead passed heuristic checks for potential buyer relevance."
            if status == ProspectStatus.CANDIDATE
            else "External lead kept for manual review; public profile does not show strong buyer intent yet."
        )
        return {
            "fit_score": score,
            "match_tags": ";".join(dict.fromkeys(tags)),
            "status": status,
            "notes": reason,
        }


def _result_snippet(page_html: str, href: str) -> str:
    # DuckDuckGo and similar result pages usually keep the snippet nearby in the same result row.
    marker = page_html.find(href)
    if marker < 0:
        return ""
    window = page_html[max(0, marker - 200) : marker + 300]
    window = re.sub(r"<[^>]+>", " ", window)
    return clean_text(window)
    return ""

