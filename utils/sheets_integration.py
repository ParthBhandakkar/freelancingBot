"""Google Sheet integration for freelance leads.

The bot writes discovered leads into the spreadsheet configured in `.env`
under `GOOGLE_SHEET_ID` on a worksheet named `GOOGLE_OUTREACH_SHEET_NAME`.
If credentials are missing, sheet operations are skipped with logs.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from config import settings
from models.schemas import FreelanceClientLead

if TYPE_CHECKING:
    from pathlib import Path

OUTREACH_COLUMNS = [
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
    "outreach_status",
    "outreach_action",
    "outreach_note",
    "connected_status",
    "last_contacted_at",
    "notes",
]


def _safe(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return "" if value is None else str(value)


class OutreachSheetStore:
    def __init__(self) -> None:
        self._client = None
        self._spreadsheet = None
        self._worksheet = None
        self._disabled = not settings.google_outreach_enabled or not settings.google_sheet_id

    def _connect(self) -> bool:
        if self._disabled:
            return False
        if self._client is not None and self._spreadsheet is not None:
            return True

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except Exception as exc:
            logger.warning("Google Sheets dependencies missing. Install gspread/google-auth. {}", exc)
            self._disabled = True
            return False

        credentials_path = Path(settings.google_credentials_file)
        if not credentials_path.is_absolute():
            credentials_path = Path(__file__).resolve().parents[1] / credentials_path

        if not credentials_path.exists():
            logger.warning("Google credentials file not found at {}. Skipping sheet sync.", credentials_path)
            self._disabled = True
            return False

        try:
            creds = Credentials.from_service_account_file(
                str(credentials_path),
                scopes=[
                    "https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive",
                ],
            )
            self._client = gspread.authorize(creds)
            self._spreadsheet = self._client.open_by_key(settings.google_sheet_id)
            return True
        except Exception as exc:
            logger.warning("Google Sheets auth/open_by_key failed: {}", exc)
            self._disabled = True
            return False

    def _ensure_sheet(self):
        if self._disabled or not self._connect():
            return None

        if self._worksheet is not None:
            return self._worksheet

        try:
            title = settings.google_outreach_sheet_name or "Outreach"
            try:
                worksheet = self._spreadsheet.worksheet(title)  # type: ignore[union-attr]
            except Exception:
                worksheet = self._find_worksheet_case_insensitive(title)
                if worksheet is None:
                    worksheet = self._spreadsheet.add_worksheet(  # type: ignore[union-attr]
                        title=title,
                        rows=max(100, settings.max_discovery_results + 20),
                        cols=max(20, len(OUTREACH_COLUMNS)),
                    )
                    logger.info("Created Google Sheet worksheet '{}'", title)

            header = worksheet.row_values(1)
            if not header or all(not _safe(col).strip() for col in header):
                worksheet.update("A1", [OUTREACH_COLUMNS], value_input_option="USER_ENTERED")
            else:
                missing = [column for column in OUTREACH_COLUMNS if column not in header]
                if missing:
                    updated_header = header + missing
                    end_col = chr(64 + len(updated_header))
                    worksheet.update(
                        f"A1:{end_col}1",
                        [updated_header],
                        value_input_option="USER_ENTERED",
                    )
            self._worksheet = worksheet
            return worksheet
        except Exception as exc:
            logger.warning("Failed to create/open Outreach worksheet: {}", exc)
            self._disabled = True
            return None

    def _find_worksheet_case_insensitive(self, title: str):
        try:
            wanted = (title or "").strip().lower()
            for worksheet in self._spreadsheet.worksheets():  # type: ignore[union-attr]
                if (worksheet.title or "").strip().lower() == wanted:
                    return worksheet
        except Exception as exc:
            logger.debug("Case-insensitive worksheet lookup failed: {}", exc)
        return None

    def _existing_profile_urls(self) -> set[str]:
        worksheet = self._ensure_sheet()
        if worksheet is None:
            return set()

        try:
            header = worksheet.row_values(1)
            url_column = [h.lower() for h in header]
            if "profile_url" not in url_column:
                return set()
            idx = url_column.index("profile_url") + 1
            return {value.strip() for value in worksheet.col_values(idx)[1:] if value.strip()}
        except Exception as exc:
            logger.warning("Unable to read existing lead profile URLs: {}", exc)
            return set()

    def _lead_row(self, lead: FreelanceClientLead) -> list[str]:
        return [
            _safe(lead.discovered_at),
            _safe(lead.full_name),
            _safe(lead.first_name),
            _safe(lead.last_name),
            _safe(lead.headline),
            _safe(lead.company),
            _safe(lead.location),
            _safe(lead.profile_url),
            _safe(lead.post_link),
            _safe(lead.profile_snippet),
            _safe(lead.matched_query),
            _safe(lead.source_platform),
            _safe(lead.source_query),
            _safe(lead.fit_score),
            _safe(lead.match_tags),
            _safe(lead.status),
            "",
            _safe(lead.outreach_action),
            _safe(lead.outreach_note),
            "",
            _safe(lead.last_contacted_at),
            _safe(lead.notes),
        ]

    def append_leads(self, leads: list[FreelanceClientLead]) -> int:
        worksheet = self._ensure_sheet()
        if worksheet is None:
            return 0

        if not leads:
            return 0

        try:
            existing_urls = self._existing_profile_urls()
        except Exception:
            existing_urls = set()

        new_rows: list[list[str]] = []
        for lead in leads:
            if not lead.profile_url or lead.profile_url in existing_urls:
                continue
            row = self._lead_row(lead)
            new_rows.append(row)
            existing_urls.add(lead.profile_url)

        if not new_rows:
            return 0

        try:
            worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
            logger.info("Wrote {} leads to Outreach sheet", len(new_rows))
            return len(new_rows)
        except Exception as exc:
            logger.warning("Failed to append leads to Outreach sheet: {}", exc)
            return 0

    def update_status(
        self,
        profile_url: str,
        status: str,
        action: str = "",
        connected_status: str = "",
        contacted_at: str = "",
        notes: str = "",
        message_text: str = "",
    ) -> bool:
        worksheet = self._ensure_sheet()
        if worksheet is None:
            return False

        try:
            header = worksheet.row_values(1)
            header_map = {name: idx + 1 for idx, name in enumerate(header)}
            if "profile_url" not in header_map:
                return False
            row_cell = worksheet.find(profile_url, in_column=header_map["profile_url"])
            if row_cell is None:
                return False

            row_num = row_cell.row
            status_col = header_map.get("outreach_status")
            action_col = header_map.get("outreach_action")
            connected_col = header_map.get("connected_status")
            contact_col = header_map.get("last_contacted_at")
            note_col = header_map.get("outreach_note")
            notes_col = header_map.get("notes")
            if (
                status_col is None
                or action_col is None
                or connected_col is None
                or contact_col is None
                or note_col is None
                or notes_col is None
            ):
                return False

            updates = [
                (status_col, status),
                (action_col, action),
                (connected_col, connected_status),
                (contact_col, contacted_at),
                (note_col, message_text),
                (notes_col, notes),
            ]
            for column, value in updates:
                worksheet.update_cell(row_num, column, _safe(value))
            return True
        except Exception as exc:
            logger.debug("Failed to update Outreach sheet status for {}: {}", profile_url, exc)
            return False

