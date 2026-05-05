"""Y Combinator startup discovery for high-value freelance leads.

Scrapes YC's public company directory to find recently funded startups
whose founders are likely to need engineering help.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from loguru import logger

from config import settings
from models.schemas import FreelanceClientLead, ProspectStatus
from utils.helpers import clean_text
from utils.lead_intent import score_buyer_intent

YC_API_URL = "https://api.ycombinator.com/v0.1/companies"
YC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# Recent YC batches to target (startups with fresh funding)
RECENT_BATCHES = ["W25", "S24", "W24", "S23", "W23"]

TECH_KEYWORDS = (
    "ai", "automation", "saas", "analytics", "backend", "api",
    "machine learning", "data", "dashboard", "platform", "software",
    "developer tools", "devtools", "infrastructure", "workflow",
)


class YCDiscovery:
    """Discover recently funded YC startups as potential freelance clients."""

    def __init__(self) -> None:
        self.seen_companies: set[str] = set()

    async def discover(
        self,
        max_results: int | None = None,
    ) -> list[FreelanceClientLead]:
        max_results = max_results or settings.max_discovery_results
        try:
            companies = await asyncio.to_thread(self._fetch_companies)
        except Exception as exc:
            logger.warning("YC discovery failed: {}", exc)
            return []

        leads: list[FreelanceClientLead] = []
        for company in companies:
            if len(leads) >= max_results:
                break
            lead = self._company_to_lead(company)
            if lead is None:
                continue
            key = lead.profile_url.lower()
            if key in self.seen_companies:
                continue
            self.seen_companies.add(key)
            leads.append(lead)

        leads.sort(key=lambda l: l.fit_score, reverse=True)
        return leads[:max_results]

    def _fetch_companies(self) -> list[dict]:
        """Fetch companies from YC API with recent batch filter."""
        all_companies: list[dict] = []

        for batch in RECENT_BATCHES:
            try:
                payload = json.dumps({"batch": batch}).encode("utf-8")
                request = Request(
                    YC_API_URL,
                    data=payload,
                    headers={**YC_HEADERS, "Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(request, timeout=20) as response:
                    data = json.loads(response.read().decode("utf-8"))

                companies = data if isinstance(data, list) else data.get("companies", [])
                all_companies.extend(companies)
                logger.info("YC batch {} returned {} companies", batch, len(companies))
            except HTTPError as exc:
                logger.debug("YC API batch {} HTTP error: {}", batch, exc.code)
                continue
            except Exception as exc:
                logger.debug("YC API batch {} error: {}", batch, exc)
                continue

        if not all_companies:
            all_companies = self._fallback_fetch()

        return all_companies

    def _fallback_fetch(self) -> list[dict]:
        """Fallback: fetch without batch filter."""
        try:
            payload = json.dumps({}).encode("utf-8")
            request = Request(
                YC_API_URL,
                data=payload,
                headers={**YC_HEADERS, "Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            companies = data if isinstance(data, list) else data.get("companies", [])
            logger.info("YC fallback returned {} companies", len(companies))
            return companies[:200]
        except Exception as exc:
            logger.warning("YC fallback fetch failed: {}", exc)
            return []

    def _company_to_lead(self, company: dict) -> FreelanceClientLead | None:
        """Convert a YC company dict to a FreelanceClientLead."""
        name = clean_text(company.get("name", ""))
        if not name:
            return None

        description = clean_text(company.get("one_liner", "") or company.get("long_description", ""))
        website = clean_text(company.get("website", "") or company.get("url", ""))
        batch = company.get("batch", "")
        team_size = company.get("team_size", 0) or 0

        # Build profile URL from YC slug or website
        slug = company.get("slug", "")
        yc_url = f"https://www.ycombinator.com/companies/{slug}" if slug else website
        if not yc_url:
            return None

        # Score relevance
        combined = f"{name} {description}".lower()
        tech_hits = [kw for kw in TECH_KEYWORDS if kw in combined]
        industry_hits = [i for i in settings.industry_keyword_list if i and i in combined]

        score = 30  # Base score for YC company (funded startup)
        tags = ["yc_startup"]

        if batch in RECENT_BATCHES[:2]:
            score += 15
            tags.append("recent_batch")
        elif batch in RECENT_BATCHES:
            score += 8

        score += len(tech_hits) * 6
        score += len(industry_hits) * 5
        tags.extend(tech_hits[:3])

        if team_size and team_size <= 15:
            score += 10
            tags.append("small_team")

        # Check description for active need signals
        intent = score_buyer_intent(name, description, settings.freelancer_focus)
        score += intent.score_boost
        tags.extend(intent.tags[:3])

        score = max(0, min(100, score))
        status = ProspectStatus.CANDIDATE if score >= settings.min_fit_score else ProspectStatus.DISCOVERED
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Extract founder names if available
        founders = company.get("founders", []) or []
        founder_names = [
            clean_text(f.get("full_name", "") or f"{f.get('first_name', '')} {f.get('last_name', '')}".strip())
            for f in founders[:2]
        ]
        founder_str = ", ".join(fn for fn in founder_names if fn)

        full_name = founder_str or name
        names = full_name.split(" ", maxsplit=1)

        return FreelanceClientLead(
            lead_id=f"{yc_url}::yc",
            full_name=full_name,
            first_name=names[0] if names else "",
            last_name=names[1] if len(names) > 1 else "",
            headline=f"{name} — {description[:100]}" if description else name,
            company=name,
            location="",
            profile_url=yc_url,
            profile_snippet=clean_text(f"YC {batch}. {description[:400]}"),
            matched_query="yc_startup_discovery",
            source_platform="YCombinator",
            source_query="yc_startup_discovery",
            fit_score=score,
            match_tags=";".join(dict.fromkeys(tags)),
            status=status,
            discovered_at=now,
            notes=f"YC {batch} startup. Team size: {team_size or 'unknown'}.",
        )
