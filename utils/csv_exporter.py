"""CSV persistence for discovered client leads."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from config import DATA_DIR
from models.schemas import FreelanceClientLead, ProspectStatus

if TYPE_CHECKING:
    from pathlib import Path


LEAD_COLUMNS = [
    "discovered_at",
    "full_name",
    "first_name",
    "last_name",
    "headline",
    "company",
    "location",
    "profile_url",
    "post_link",
    "profile_snippet",
    "matched_query",
    "source_platform",
    "source_query",
    "fit_score",
    "match_tags",
    "status",
    "outreach_action",
    "outreach_note",
    "last_contacted_at",
    "notes",
]


def _lead_path(filename: str | None = None) -> Path:
    return DATA_DIR / (filename or "freelance_leads.csv")


def _lead_to_row(lead: FreelanceClientLead) -> dict[str, str]:
    return {
        "discovered_at": lead.discovered_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "full_name": lead.full_name,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "headline": lead.headline,
        "company": lead.company,
        "location": lead.location,
        "profile_url": lead.profile_url,
        "post_link": lead.post_link,
        "profile_snippet": lead.profile_snippet,
        "matched_query": lead.matched_query,
        "source_platform": lead.source_platform,
        "source_query": lead.source_query,
        "fit_score": str(lead.fit_score),
        "match_tags": lead.match_tags,
        "status": lead.status.value,
        "outreach_action": lead.outreach_action,
        "outreach_note": lead.outreach_note,
        "last_contacted_at": lead.last_contacted_at,
        "notes": lead.notes,
    }


def _row_to_lead(row: dict[str, str]) -> FreelanceClientLead:
    status_val = (row.get("status") or "").strip() or ProspectStatus.DISCOVERED.value
    try:
        status = ProspectStatus(status_val)
    except Exception:
        status = ProspectStatus.DISCOVERED

    return FreelanceClientLead(
        discovered_at=row.get("discovered_at", ""),
        full_name=row.get("full_name", ""),
        first_name=row.get("first_name", ""),
        last_name=row.get("last_name", ""),
        headline=row.get("headline", ""),
        company=row.get("company", ""),
        location=row.get("location", ""),
        profile_url=row.get("profile_url", ""),
        post_link=row.get("post_link", ""),
        profile_snippet=row.get("profile_snippet", ""),
        matched_query=row.get("matched_query", ""),
        source_platform=row.get("source_platform", ""),
        source_query=row.get("source_query", ""),
        fit_score=int(row.get("fit_score", "0") or 0),
        match_tags=row.get("match_tags", ""),
        status=status,
        outreach_action=row.get("outreach_action", ""),
        outreach_note=row.get("outreach_note", ""),
        last_contacted_at=row.get("last_contacted_at", ""),
        notes=row.get("notes", ""),
    )


def load_leads(filename: str | None = None) -> list[FreelanceClientLead]:
    path = _lead_path(filename)
    if not path.exists():
        return []

    _ensure_lead_file_schema(path)

    leads: list[FreelanceClientLead] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(_row_to_lead(row))
    return leads


def append_leads(leads: list[FreelanceClientLead], filename: str | None = None) -> tuple[int, int]:
    path = _lead_path(filename)
    _ensure_lead_file_schema(path)
    existing_urls = {lead.profile_url for lead in load_leads(filename)}
    added = 0

    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS)
        if f.tell() == 0:
            writer.writeheader()

        for lead in leads:
            if not lead.profile_url or lead.profile_url in existing_urls:
                continue
            writer.writerow(_lead_to_row(lead))
            existing_urls.add(lead.profile_url)
            added += 1

    return added, len(leads)


def save_leads(leads: list[FreelanceClientLead], filename: str | None = None) -> None:
    path = _lead_path(filename)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS)
        writer.writeheader()
        for lead in leads:
            writer.writerow(_lead_to_row(lead))


def load_pending_leads(
    status_values: list[ProspectStatus],
    filename: str | None = None,
    min_score: int = 0,
) -> list[FreelanceClientLead]:
    return [
        lead
        for lead in load_leads(filename)
        if lead.status in status_values and lead.fit_score >= min_score
    ]


def update_lead_status(
    profile_url: str,
    status: ProspectStatus | None = None,
    outreach_action: str | None = None,
    outreach_note: str | None = None,
    last_contacted_at: str | None = None,
    notes: str | None = None,
    filename: str | None = None,
) -> bool:
    path = _lead_path(filename)
    if not path.exists():
        return False

    _ensure_lead_file_schema(path)

    rows = load_leads(filename)
    updated = False

    for row in rows:
        if row.profile_url != profile_url:
            continue
        if status is not None:
            row.status = status
        if outreach_action is not None:
            row.outreach_action = outreach_action
        if outreach_note is not None:
            row.outreach_note = outreach_note
        if last_contacted_at is not None:
            row.last_contacted_at = last_contacted_at
        if notes is not None:
            row.notes = notes
        updated = True

    if updated:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS)
            writer.writeheader()
            for row in rows:
                writer.writerow(_lead_to_row(row))
    return updated


def _ensure_lead_file_schema(path: Path) -> None:
    if not path.exists():
        return

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        if header == LEAD_COLUMNS:
            return
        rows = [_row_to_lead(row) for row in reader]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_COLUMNS)
        writer.writeheader()
        for lead in rows:
            writer.writerow(_lead_to_row(lead))

