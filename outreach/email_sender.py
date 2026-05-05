"""SMTP cold email sender with rate limiting and sequence support.

Sends cold emails using configurable SMTP credentials. Supports a 3-step
sequence: initial pitch, follow-up 1, follow-up 2.
"""
from __future__ import annotations

import asyncio
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from config import settings
from models.schemas import FreelanceClientLead, OutreachResult, OutreachResultStatus


class EmailSender:
    """Send cold emails via SMTP with daily rate limiting."""

    def __init__(self) -> None:
        self._daily_count = 0
        self._last_reset_date: str = ""

    @property
    def available(self) -> bool:
        return settings.has_smtp_config

    @property
    def under_limit(self) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._last_reset_date:
            self._daily_count = 0
            self._last_reset_date = today
        return self._daily_count < settings.email_daily_limit

    async def send_cold_email(
        self, lead: FreelanceClientLead, sequence_step: int = 1
    ) -> OutreachResult:
        """Send a cold email to a lead.

        sequence_step: 1 = initial, 2 = follow-up 1, 3 = follow-up 2
        """
        if not self.available:
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.SKIPPED,
                action_taken="email_not_configured",
                notes="SMTP not configured. Set SMTP_HOST/SMTP_USER in .env.",
            )

        if not lead.email:
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.SKIPPED,
                action_taken="no_email",
                notes="No email address available for this lead.",
            )

        if not self.under_limit:
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.SKIPPED,
                action_taken="daily_limit_reached",
                notes=f"Daily email limit ({settings.email_daily_limit}) reached.",
            )

        subject, body = self._build_email(lead, sequence_step)

        try:
            sent = await asyncio.to_thread(
                self._smtp_send, lead.email, subject, body
            )
            if sent:
                self._daily_count += 1
                step_name = {1: "initial", 2: "followup_1", 3: "followup_2"}.get(
                    sequence_step, "initial"
                )
                return OutreachResult(
                    lead=lead,
                    status=OutreachResultStatus.EMAIL_SENT,
                    action_taken=f"email_{step_name}_sent",
                    message_text=body,
                    notes=f"Email sent to {lead.email} (step {sequence_step}).",
                    sent_at=datetime.now(),
                )
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.FAILED,
                action_taken="email_send_failed",
                notes="SMTP send returned failure.",
            )
        except Exception as exc:
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.FAILED,
                action_taken="email_error",
                notes=f"Email send error: {str(exc)[:200]}",
                errors=[str(exc)],
            )

    def _build_email(
        self, lead: FreelanceClientLead, step: int
    ) -> tuple[str, str]:
        """Build subject and body for the given sequence step."""
        fmt = {
            "first_name": lead.first_name or lead.full_name.split(" ")[0],
            "full_name": lead.full_name,
            "company": lead.company or "your company",
            "headline": lead.headline,
            "portfolio_url": settings.portfolio_url,
            "freelancer_name": settings.freelancer_name,
            "freelancer_role": settings.freelancer_role,
        }

        if step == 2:
            subject = settings.email_followup_1_subject.format(**fmt)
            body = settings.email_followup_1_body.format(**fmt)
        elif step == 3:
            subject = settings.email_followup_2_subject.format(**fmt)
            body = settings.email_followup_2_body.format(**fmt)
        else:
            subject = settings.email_subject_template.format(**fmt)
            body = settings.email_body_template.format(**fmt)

        return subject, body

    def _smtp_send(self, to_email: str, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        msg = MIMEMultipart("alternative")
        from_name = settings.smtp_from_name or settings.freelancer_name
        from_email = settings.smtp_from_email or settings.smtp_user
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(from_email, to_email, msg.as_string())
            logger.info("Email sent to {}", to_email)
            return True
        except Exception as exc:
            logger.warning("SMTP send failed to {}: {}", to_email, exc)
            raise


# Singleton
email_sender = EmailSender()
