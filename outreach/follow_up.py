"""Follow-up manager for lead nurturing.

Identifies leads that were contacted but haven't replied, and generates
follow-up messages on a configurable cadence (default: day 3 and day 7).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger

from config import settings
from models.schemas import FreelanceClientLead, ProspectStatus
from utils.csv_exporter import load_leads
from utils.helpers import clean_text


# Statuses that are eligible for follow-up
FOLLOWUP_1_ELIGIBLE = {
    ProspectStatus.MESSAGE_SENT,
    ProspectStatus.EMAIL_SENT,
}

FOLLOWUP_2_ELIGIBLE = {
    ProspectStatus.FOLLOW_UP_1,
    ProspectStatus.EMAIL_FOLLOW_UP_1,
}


class FollowUpManager:
    """Manage automated follow-up sequences."""

    def get_due_followups(
        self,
        filename: str | None = None,
        max_results: int | None = None,
    ) -> list[tuple[FreelanceClientLead, int]]:
        """Return leads due for follow-up with their step number.

        Returns list of (lead, step) where step is 1 or 2.
        """
        max_results = max_results or settings.max_outreach_per_run
        leads = load_leads(filename)
        now = datetime.now()
        due: list[tuple[FreelanceClientLead, int]] = []

        for lead in leads:
            if len(due) >= max_results:
                break

            if not lead.last_contacted_at:
                continue

            try:
                last_contact = datetime.strptime(
                    lead.last_contacted_at, "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, TypeError):
                continue

            days_since = (now - last_contact).days

            # Check for follow-up 1
            if (
                lead.status in FOLLOWUP_1_ELIGIBLE
                and days_since >= settings.followup_1_delay_days
            ):
                due.append((lead, 1))
                continue

            # Check for follow-up 2
            if (
                lead.status in FOLLOWUP_2_ELIGIBLE
                and days_since >= settings.followup_2_delay_days
            ):
                due.append((lead, 2))
                continue

        logger.info("Found {} leads due for follow-up", len(due))
        return due

    @staticmethod
    def build_followup_message(
        lead: FreelanceClientLead, step: int
    ) -> str:
        """Build the follow-up message text for the given step."""
        fmt = {
            "first_name": lead.first_name or lead.full_name.split(" ")[0],
            "full_name": lead.full_name,
            "company": lead.company or "your team",
            "portfolio_url": settings.portfolio_url,
            "freelancer_name": settings.freelancer_name,
        }

        if step == 2:
            template = settings.followup_2_template
        else:
            template = settings.followup_1_template

        return clean_text(template.format(**fmt))

    @staticmethod
    def next_status(lead: FreelanceClientLead, step: int) -> ProspectStatus:
        """Determine the next status after a follow-up."""
        if step == 1:
            if lead.status in {ProspectStatus.EMAIL_SENT}:
                return ProspectStatus.EMAIL_FOLLOW_UP_1
            return ProspectStatus.FOLLOW_UP_1
        if step == 2:
            if lead.status in {ProspectStatus.EMAIL_FOLLOW_UP_1}:
                return ProspectStatus.EMAIL_FOLLOW_UP_2
            return ProspectStatus.FOLLOW_UP_2
        return ProspectStatus.FOLLOW_UP_DONE
