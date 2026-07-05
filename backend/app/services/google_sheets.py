import os
import json
import logging
import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session
from ..models import Lead

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_client():
    creds_json = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "")
    creds_file = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "")

    if creds_file:
        logger.info("Reading credentials from file: %s", creds_file)
        if not os.path.isabs(creds_file):
            creds_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), creds_file)
        try:
            with open(creds_file) as f:
                creds_dict = json.load(f)
        except Exception as e:
            return None, f"Failed to read credentials file: {str(e)}"
    elif creds_json:
        try:
            creds_dict = json.loads(creds_json)
        except json.JSONDecodeError:
            return None, (
                "GOOGLE_SHEETS_CREDENTIALS is not valid JSON. "
                "If you pasted multi-line JSON, either:\n"
                "1. Set GOOGLE_SHEETS_CREDENTIALS_FILE to the path of your JSON file, or\n"
                "2. Collapse the JSON to a single line in .env"
            )
        except Exception as e:
            return None, f"Failed to authenticate: {str(e)}"
    else:
        return None, (
            "No credentials found. Set GOOGLE_SHEETS_CREDENTIALS (inline JSON) "
            "or GOOGLE_SHEETS_CREDENTIALS_FILE (path to JSON file) in .env"
        )

    try:
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        logger.info("Google Sheets auth successful")
        return client, None
    except Exception as e:
        return None, f"Failed to authenticate: {str(e)}"


def export_leads_to_sheet(spreadsheet_id: str, db: Session) -> dict:
    client, error = get_client()
    if error:
        return {"success": False, "error": error}

    try:
        sheet = client.open_by_key(spreadsheet_id)
        worksheet = sheet.get_worksheet(0)
        if not worksheet:
            worksheet = sheet.add_worksheet(title="Leads", rows=1000, cols=20)
    except Exception as e:
        return {"success": False, "error": f"Sheet access failed: {str(e)}. Make sure the sheet is shared with the service account email."}

    leads = db.query(Lead).order_by(Lead.created_at.desc()).all()

    headers = [
        "ID", "Name", "Business Name", "Platform", "Profile URL",
        "Website URL", "Email", "Phone", "City", "Niche",
        "Followers", "Online Presence Score", "Lead Score",
        "Flaws", "Analysis Notes", "Status", "Response",
        "Asset Generated", "Asset URL", "Outreach Message",
        "Created At", "Updated At",
    ]

    rows = [headers]
    for lead in leads:
        rows.append([
            lead.id, lead.name, lead.business_name, lead.platform,
            lead.profile_url or "", lead.website_url or "",
            lead.email or "", lead.phone or "", lead.city or "",
            lead.niche or "", lead.followers or 0,
            lead.online_presence_score or 0, lead.lead_score or 0,
            lead.flaws or "", lead.analysis_notes or "",
            lead.status or "new", lead.response or "pending",
            "Yes" if lead.asset_generated else "No",
            lead.asset_url or "", lead.outreach_message or "",
            str(lead.created_at or ""), str(lead.updated_at or ""),
        ])

    worksheet.clear()
    worksheet.update(range_name="A1", values=rows)

    return {
        "success": True,
        "total_leads": len(leads),
        "sheet_id": spreadsheet_id,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
    }
