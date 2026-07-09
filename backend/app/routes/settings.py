import os
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.settings_service import get_all_settings, set_setting, SETTING_DEFAULTS

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    my_name: Optional[str] = None
    my_company: Optional[str] = None
    my_website: Optional[str] = None
    calendly_link: Optional[str] = None
    email_signature: Optional[str] = None
    services_offered: Optional[str] = None
    daily_send_limit: Optional[str] = None
    auto_send_followups: Optional[str] = None


@router.get("")
def read_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)


@router.put("")
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    updated = {}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in SETTING_DEFAULTS and value is not None:
            set_setting(db, key, value)
            updated[key] = value
    return {"updated": updated, "settings": get_all_settings(db)}


@router.get("/status")
def integration_status(db: Session = Depends(get_db)):
    """Which integrations are configured — shown on the Settings page so the
    user knows what works without reading .env."""
    return {
        "google_places": bool(os.getenv("GOOGLE_API_KEY")),
        "yelp": bool(os.getenv("YELP_API_KEY")),
        "hunter": bool(os.getenv("HUNTER_API_KEY")),
        "smtp": bool(os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
        "google_sheets": bool(os.getenv("GOOGLE_SHEETS_ID")),
    }
