import os
from sqlalchemy.orm import Session
from ..models import Setting

# Settings the user can edit in the UI. Values are seeded once from .env
# (if present) and stored in the DB from then on.
SETTING_DEFAULTS = {
    "my_name": lambda: os.getenv("MY_NAME", "") or os.getenv("SMTP_FROM_NAME", ""),
    "my_company": lambda: os.getenv("MY_COMPANY", ""),
    "my_website": lambda: os.getenv("MY_WEBSITE", ""),
    "calendly_link": lambda: os.getenv("CALENDLY_LINK", ""),
    "email_signature": lambda: "",
    "services_offered": lambda: "website design, redesign, SEO and online presence for local businesses",
    "daily_send_limit": lambda: "25",
    "auto_send_followups": lambda: "true",
}


def get_setting(db: Session, key: str) -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is not None:
        return row.value or ""
    default = SETTING_DEFAULTS.get(key, lambda: "")()
    row = Setting(key=key, value=default)
    db.add(row)
    db.commit()
    return default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def get_all_settings(db: Session) -> dict:
    return {key: get_setting(db, key) for key in SETTING_DEFAULTS}


def get_sender_identity(db: Session) -> dict:
    """Everything the outreach templates need about *you*."""
    return {
        "my_name": get_setting(db, "my_name") or "there",
        "my_company": get_setting(db, "my_company"),
        "my_website": get_setting(db, "my_website"),
        "calendly_link": get_setting(db, "calendly_link"),
        "email_signature": get_setting(db, "email_signature"),
        "services_offered": get_setting(db, "services_offered"),
    }
