"""Automatic follow-up sender.

Runs hourly: finds sequence steps whose delay has elapsed and auto-sends the
email ones (respecting the daily send limit and the auto-send toggle from
Settings). Call/DM steps are never auto-executed — they appear in the Today
queue for you to do by hand.
"""

import logging
from datetime import datetime, time as dtime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..database import SessionLocal
from ..models import OutreachSequenceStep

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def emails_sent_today(db) -> int:
    today_start = datetime.combine(datetime.utcnow().date(), dtime.min)
    return (
        db.query(OutreachSequenceStep)
        .filter(OutreachSequenceStep.action_type == "email")
        .filter(OutreachSequenceStep.status == "sent")
        .filter(OutreachSequenceStep.sent_at >= today_start)
        .count()
    )


async def send_due_followups():
    from ..routes.outreach import get_due_steps, execute_step
    from .settings_service import get_setting

    db = SessionLocal()
    try:
        if get_setting(db, "auto_send_followups").lower() not in ("true", "1", "yes"):
            return

        try:
            limit = int(get_setting(db, "daily_send_limit") or "25")
        except ValueError:
            limit = 25

        already_sent = emails_sent_today(db)
        budget = max(0, limit - already_sent)
        if budget == 0:
            logger.info("Auto follow-ups: daily limit reached (%d), skipping", limit)
            return

        due = get_due_steps(db)
        sent = 0
        for seq, step, lead in due:
            if sent >= budget:
                break
            if step.action_type != "email" or not lead.email:
                continue  # manual channels stay in the Today queue
            try:
                result = await execute_step(seq, step, lead, db)
                if result.get("sent"):
                    sent += 1
                    logger.info("Auto-sent follow-up to %s (lead #%s, step %d)", lead.email, lead.id, step.step_order)
            except Exception as e:
                logger.error("Auto follow-up failed for lead #%s: %s", lead.id, e)
        if sent:
            logger.info("Auto follow-ups: sent %d email(s), %d/%d daily budget used", sent, already_sent + sent, limit)
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(send_due_followups, "interval", hours=1, id="followups", replace_existing=True)
    scheduler.start()
    logger.info("Follow-up scheduler started (checks hourly)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
