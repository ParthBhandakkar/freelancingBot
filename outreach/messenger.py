"""LinkedIn outreach automation for freelance leads."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from browser.engine import BrowserEngine
from config import settings
from llm.client import llm_client
from llm.prompts import CLIENT_MESSAGE_SYSTEM, CLIENT_MESSAGE_USER, ICEBREAKER_SYSTEM, ICEBREAKER_USER
from models.schemas import FreelanceClientLead, OutreachResult, OutreachResultStatus
from outreach.linkedin_profile_signals import (
    JS_HEADER_SHOWS_2ND_OR_3RD,
    JS_PENDING_IN_HEADER,
    JS_TEXT_INDICATES_1ST_DEGREE,
    PENDING_INVITE_SELECTORS,
)
from utils.helpers import clean_text, human_delay

_PM = "main"

MESSAGE_BUTTON_SELECTORS = [
    f"{_PM} button:has-text('Message')",
    f"{_PM} a:has-text('Message')",
    f"{_PM} button[aria-label*='Message']",
    f"{_PM} a[aria-label*='Message']",
]

CONNECT_BUTTON_SELECTORS = [
    f"{_PM} button:has-text('Connect')",
    f"{_PM} button[aria-label*='Connect']",
    f"{_PM} button[aria-label*='Invite']",
]

CONNECT_MENU_SELECTORS = [
    "div[role='menu'] *:has-text('Connect')",
    "li:has-text('Connect')",
    "button:has-text('Connect')",
    "div[role='button']:has-text('Connect')",
]

ADD_NOTE_SELECTORS = [
    "button:has-text('Add a note')",
    "button[aria-label*='Add a note']",
    "button[aria-label*='Add note']",
]

SEND_INVITE_SELECTORS = [
    "button:has-text('Send without a note')",
    "div[role='button']:has-text('Send without a note')",
    "button:has-text('Send')",
    "button:has-text('Done')",
    "button:has-text('Send now')",
    "button[aria-label*='Send invitation']",
]

MESSAGE_INPUT_SELECTORS = [
    ".msg-form__contenteditable[contenteditable='true']",
    "div.msg-form__contenteditable",
    "div.msg-form__message-texteditor [contenteditable='true']",
    "div[data-test-id='message-compose-box'] [contenteditable='true']",
    "div[role='dialog'] .msg-form__contenteditable",
    "div[role='dialog'] [contenteditable='true'][role='textbox']",
    "aside [contenteditable='true'][role='textbox']",
    "div[class*='msg-overlay'] [contenteditable='true']",
    "div[role='textbox'][contenteditable='true']",
    "textarea[name='message']",
    "textarea",
]

SEND_MESSAGE_SELECTORS = [
    "div[role='dialog'] button.msg-form__send-button",
    "button.msg-form__send-button",
    "div[role='dialog'] button[aria-label*='Send']",
    "button[aria-label*='Send message']",
    "button[aria-label='Send now']",
    "div[role='dialog'] button:has-text('Send')",
]

FIRST_DEGREE_SELECTORS = [
    f"{_PM} span.dist-value:has-text('1st')",
    f"{_PM} span:has-text('1st degree connection')",
    f"{_PM} li-icon[type='1st-degree']",
]


class ClientOutreachMessenger:
    def __init__(self, browser: BrowserEngine) -> None:
        self.browser = browser

    async def reach_out_to_lead(
        self, lead: FreelanceClientLead, use_llm: bool = True
    ) -> OutreachResult:
        await self._open_profile(lead)

        if await self._pending_invite_visible():
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.CONNECT_REQUESTED,
                action_taken="pending_detected",
                connected_status="pending",
                notes="Connection request already pending.",
            )

        is_first_degree = await self._is_first_degree_connection()
        if is_first_degree:
            message = await self._build_message(lead, use_llm=use_llm)
            sent, notes = await self._send_message_flow(message)
            if sent:
                return OutreachResult(
                    lead=lead,
                    status=OutreachResultStatus.MESSAGE_SENT,
                    action_taken="message_existing_connection",
                    connected_status="first_degree",
                    message_text=message,
                    notes=notes,
                )
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.CONNECTED,
                action_taken="message_unavailable_existing_connection",
                connected_status="first_degree",
                message_text=message,
                notes=notes or "Already connected, but could not send a message.",
            )

        return await self.send_connection_request(lead)

    async def send_connection_request(
        self, lead: FreelanceClientLead, use_llm: bool = False
    ) -> OutreachResult:
        await self._open_profile(lead)

        if await self._pending_invite_visible():
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.CONNECT_REQUESTED,
                action_taken="pending_detected",
                connected_status="pending",
                notes="Connection request already pending.",
            )

        if await self._is_first_degree_connection():
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.CONNECTED,
                action_taken="already_connected",
                connected_status="first_degree",
                notes="Profile is already a first-degree connection.",
            )

        status, action, notes = await self._connect_flow()
        return OutreachResult(
            lead=lead,
            status=status,
            action_taken=action,
            connected_status="pending" if status == OutreachResultStatus.CONNECT_REQUESTED else "",
            notes=notes,
        )

    async def send_message_if_ready(
        self, lead: FreelanceClientLead, use_llm: bool = True
    ) -> OutreachResult:
        await self._open_profile(lead)

        if await self._pending_invite_visible():
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.CONNECT_REQUESTED,
                action_taken="pending_detected",
                connected_status="pending",
                notes="Invite is still pending. Message skipped for now.",
            )

        if not await self._is_first_degree_connection():
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.SKIPPED,
                action_taken="not_connected_yet",
                notes="Profile is not first-degree yet, so message was not sent.",
            )

        if not await self._has_any_selector(MESSAGE_BUTTON_SELECTORS):
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.CONNECTED,
                action_taken="message_button_missing",
                connected_status="first_degree",
                notes="Profile is connected, but Message is not available on the page.",
            )

        message = await self._build_message(lead, use_llm=use_llm, use_pitch=True)
        sent, notes = await self._send_message_flow(message)
        if sent:
            return OutreachResult(
                lead=lead,
                status=OutreachResultStatus.MESSAGE_SENT,
                action_taken="message_sent_after_connection_check",
                connected_status="first_degree",
                message_text=message,
                notes=notes,
            )

        return OutreachResult(
            lead=lead,
            status=OutreachResultStatus.FAILED,
            action_taken="message_failed_after_connection_check",
            connected_status="first_degree",
            message_text=message,
            notes=notes or "Could not complete the message composer flow.",
        )

    async def _open_profile(self, lead: FreelanceClientLead) -> None:
        logger.info("Opening LinkedIn lead profile {}", lead.profile_url)
        await self.browser.goto(lead.profile_url, wait_until="domcontentloaded")
        await human_delay(settings.outreach_delay_min, settings.outreach_delay_max)
        await self._dismiss_popups()
        await self._scroll_to_profile_top()

    async def _build_message(self, lead: FreelanceClientLead, *, use_llm: bool, use_pitch: bool = False) -> str:
        if use_pitch and settings.soft_pitch_enabled:
            template = settings.outreach_pitch_message_template
        else:
            template = settings.outreach_message
        message = self._render_template(template, lead, default_signature=False)
        if use_llm and settings.has_llm_key and await llm_client.is_available():
            drafted = await self._draft_message_with_llm(lead)
            if drafted:
                message = drafted
            else:
                # Try icebreaker prepend on template
                icebreaker = await self._generate_icebreaker(lead)
                if icebreaker:
                    message = f"{icebreaker} {message}"
        return clean_text(message)

    def _truncate_connect_note(self, text: str) -> str:
        note = clean_text(text)
        if len(note) <= 300:
            return note
        return note[:297].rstrip() + "..."

    async def _draft_message_with_llm(self, lead: FreelanceClientLead) -> str:
        try:
            prompt = CLIENT_MESSAGE_USER.format(
                freelancer_name=settings.freelancer_name,
                freelancer_role=settings.freelancer_role,
                portfolio_url=settings.portfolio_url,
                freelancer_summary=settings.freelancer_summary,
                first_name=lead.first_name or lead.full_name.split(" ")[0],
                headline=lead.headline,
                company=lead.company,
                fit_reason=(lead.notes or lead.matched_query or "")[:180],
            )
            response = await llm_client.chat_json(
                system_prompt=CLIENT_MESSAGE_SYSTEM,
                user_message=prompt,
                max_tokens=600,
                temperature=0.35,
            )
            if isinstance(response, dict):
                text = str(response.get("message", "")).strip()
                if text:
                    return clean_text(text)
        except Exception as exc:
            logger.debug("LLM outreach generation failed: {}", exc)
        return ""

    async def _generate_icebreaker(self, lead: FreelanceClientLead) -> str:
        """Generate a hyper-personalized icebreaker using the LLM."""
        if not settings.has_llm_key:
            return ""
        try:
            prompt = ICEBREAKER_USER.format(
                full_name=lead.full_name,
                headline=lead.headline,
                company=lead.company or "their company",
                snippet=(lead.profile_snippet or lead.notes or "")[:300],
                query=lead.matched_query or "",
            )
            response = await llm_client.chat_json(
                system_prompt=ICEBREAKER_SYSTEM,
                user_message=prompt,
                max_tokens=200,
                temperature=0.4,
                request_name="icebreaker",
            )
            if isinstance(response, dict):
                icebreaker = str(response.get("icebreaker", "")).strip()
                if icebreaker and len(icebreaker) > 10:
                    logger.debug("Generated icebreaker: {}", icebreaker[:100])
                    return icebreaker
        except Exception as exc:
            logger.debug("Icebreaker generation failed: {}", exc)
        return ""

    def _render_template(
        self,
        template: str,
        lead: FreelanceClientLead,
        default_signature: bool = True,
    ) -> str:
        base = template.format(
            first_name=lead.first_name or lead.full_name.split(" ")[0],
            full_name=lead.full_name,
            company=lead.company,
            headline=lead.headline,
            location=lead.location,
            portfolio_url=settings.portfolio_url,
            freelancer_name=settings.freelancer_name,
            freelancer_role=settings.freelancer_role,
            match_tags=lead.match_tags,
            matched_query=lead.matched_query,
        ).strip()
        if default_signature and settings.outreach_signature_text:
            return f"{base}\n\n{settings.outreach_signature_text}"
        return base

    async def _connect_flow(self) -> tuple[OutreachResultStatus, str, str]:
        if await self._has_any_selector(PENDING_INVITE_SELECTORS):
            return (
                OutreachResultStatus.CONNECT_REQUESTED,
                "pending_detected",
                "Connection request already pending.",
            )

        connected = False
        if await self._has_connect_in_header_js():
            connected = await self._js_click_connect_in_header()
            if not connected:
                connected = await self._click_any_selector(CONNECT_BUTTON_SELECTORS, timeout=2500)

        if not connected:
            more_opened = await self._js_click_profile_more_button()
            if more_opened:
                await human_delay(0.5, 0.9)
                connected = await self._click_connect_in_open_menu()
                if not connected:
                    connected = await self._click_any_selector(CONNECT_MENU_SELECTORS, timeout=2000)

        if not connected:
            return (
                OutreachResultStatus.SKIPPED,
                "connect_unavailable",
                "Connect was not available on this profile.",
            )

        await human_delay(1.0, 1.8)
        await self._dismiss_popups()

        sent = await self._click_any_selector(SEND_INVITE_SELECTORS, timeout=5000)
        if not sent:
            if await self._pending_invite_visible():
                return (
                    OutreachResultStatus.CONNECT_REQUESTED,
                    "connect_requested",
                    "Connection invite appears to be pending already.",
                )
            return (
                OutreachResultStatus.FAILED,
                "connect_submit_failed",
                "Could not submit the connection request.",
            )

        await human_delay(1.0, 2.0)
        if await self._pending_invite_visible():
            return (
                OutreachResultStatus.CONNECT_REQUESTED,
                "connect_requested",
                "Connection request sent successfully.",
            )
        if await self._is_first_degree_connection():
            return (
                OutreachResultStatus.CONNECTED,
                "already_connected_after_invite",
                "Profile appears to be first-degree after the connection flow.",
            )
        return (
            OutreachResultStatus.CONNECT_REQUESTED,
            "connect_requested",
            "Connection request submitted.",
        )

    async def _send_message_flow(self, message_text: str) -> tuple[bool, str]:
        clicked = await self._click_any_selector(MESSAGE_BUTTON_SELECTORS, timeout=4000)
        if not clicked:
            return False, "Message button not available."

        await human_delay(1.2, 2.0)
        await self._dismiss_popups()

        input_locator = await self._find_visible_locator(
            MESSAGE_INPUT_SELECTORS,
            timeout=12000,
            prefer_last=True,
        )
        if input_locator is None:
            return False, "Message composer input not found."

        typed = await self._type_message(input_locator, message_text)
        if not typed:
            typed = await self._set_composer_text_last(message_text)
        if not typed:
            return False, "Failed to type the message."

        await human_delay(0.8, 1.4)
        sent = await self._click_send_button()
        if not sent:
            await self._dismiss_popups()
            await human_delay(0.5, 1.0)
            sent = await self._click_send_button()
        if not sent:
            return False, "Failed to click send."
        await human_delay(0.8, 1.6)
        return True, "Message sent successfully."

    async def _dismiss_popups(self) -> None:
        await self.browser.dismiss_linkedin_popups()
        js = """
(() => {
  let closed = 0;
  const isVis = el => {
    if (!el || !el.offsetParent) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  for (const btn of document.querySelectorAll(
    'button[aria-label="Dismiss"], button[aria-label="Close"], '
    + 'button[data-test-modal-close-btn], .artdeco-modal__dismiss'
  )) {
    if (!isVis(btn)) continue;
    let c = btn.parentElement;
    for (let i = 0; i < 12 && c; i++, c = c.parentElement) {
      if (/premium|upgrade|free trial|job search|inmail|top applicant|personalized/i.test(
        (c.innerText || '').slice(0, 600)
      )) {
        btn.click();
        closed++;
        break;
      }
    }
  }
  for (const btn of document.querySelectorAll(
    'button[aria-label="Not now"], button[aria-label="Skip"], button[aria-label="Dismiss"]'
  )) {
    if (isVis(btn)) {
      btn.click();
      closed++;
    }
  }
  return closed;
})()
"""
        try:
            await self.browser.evaluate(js)
        except Exception:
            pass
        await asyncio.sleep(0.3)

    async def _scroll_to_profile_top(self) -> None:
        try:
            await self.browser.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.4)
        except Exception:
            pass

    async def _has_any_selector(self, selectors: list[str]) -> bool:
        for selector in selectors:
            try:
                locator = self.browser.page.locator(selector).first
                if await locator.count() > 0 and await locator.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _click_any_selector(self, selectors: list[str], timeout: int = 5000) -> bool:
        for selector in selectors:
            try:
                if await self.browser.safe_click(selector, timeout=timeout):
                    await human_delay(0.8, 1.4)
                    return True
            except Exception:
                continue
        return False

    async def _find_visible_locator(
        self,
        selectors: list[str],
        timeout: int = 8000,
        *,
        max_per_selector: int = 16,
        prefer_last: bool = False,
    ):
        deadline = asyncio.get_event_loop().time() + (timeout / 1000)
        while asyncio.get_event_loop().time() < deadline:
            for selector in selectors:
                try:
                    group = self.browser.page.locator(selector)
                    count = await group.count()
                    limit = min(count, max_per_selector)
                    indices = range(limit - 1, -1, -1) if prefer_last else range(limit)
                    for idx in indices:
                        locator = group.nth(idx)
                        if await locator.is_visible():
                            return locator
                except Exception:
                    continue
            await asyncio.sleep(0.35)
        return None

    async def _type_message(self, locator, message_text: str) -> bool:
        try:
            await self.browser.human_type(locator, message_text, clear_first=True)
            return True
        except Exception:
            return await self._set_composer_text(message_text, MESSAGE_INPUT_SELECTORS)

    async def _click_send_button(self) -> bool:
        locator = await self._find_visible_locator(
            SEND_MESSAGE_SELECTORS,
            timeout=8000,
            prefer_last=True,
        )
        if locator is None:
            return False

        try:
            disabled = await locator.get_attribute("disabled")
            aria_disabled = await locator.get_attribute("aria-disabled")
            if disabled is not None or str(aria_disabled).lower() == "true":
                return False
            await self.browser.human_click(locator)
            return True
        except Exception:
            return False

    async def _set_composer_text(self, text: str, selectors: list[str]) -> bool:
        js = f"""
(() => {{
  const selectors = {json.dumps(selectors)};
  const text = {json.dumps(text)};
  for (const selector of selectors) {{
    const el = document.querySelector(selector);
    if (!el) continue;
    el.focus();
    if ('value' in el) {{
      el.value = text;
      el.dispatchEvent(new Event('input', {{ bubbles: true }}));
      el.dispatchEvent(new Event('change', {{ bubbles: true }}));
      return true;
    }}
    if (el.isContentEditable) {{
      el.innerHTML = '';
      el.textContent = text;
      el.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: text, inputType: 'insertText' }}));
      return true;
    }}
  }}
  return false;
}})()
"""
        try:
            return bool(await self._evaluate_unwrapped(js))
        except Exception:
            return False

    async def _set_composer_text_last(self, text: str) -> bool:
        payload = json.dumps(text)
        js = f"""
(() => {{
  const text = {payload};
  let last = null;
  for (const sel of [
    '.msg-form__contenteditable[contenteditable="true"]',
    'div.msg-form__contenteditable',
    'div[role="textbox"][contenteditable="true"]',
    'textarea'
  ]) {{
    for (const el of document.querySelectorAll(sel)) {{
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      const st = window.getComputedStyle(el);
      if (st.display === 'none' || st.visibility === 'hidden') continue;
      last = el;
    }}
  }}
  if (!last) return false;
  last.focus();
  if ('value' in last) {{
    last.value = text;
    last.dispatchEvent(new Event('input', {{ bubbles: true }}));
    last.dispatchEvent(new Event('change', {{ bubbles: true }}));
    return true;
  }}
  if (last.isContentEditable) {{
    last.innerHTML = '';
    last.textContent = text;
    last.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: text, inputType: 'insertText' }}));
    return true;
  }}
  return false;
}})()
"""
        try:
            return bool(await self._evaluate_unwrapped(js))
        except Exception:
            return False

    async def _pending_invite_visible(self) -> bool:
        if await self._has_any_selector(PENDING_INVITE_SELECTORS):
            return True
        return await self._eval_bool(JS_PENDING_IN_HEADER)

    async def _header_shows_2nd_or_3rd_degree(self) -> bool:
        return await self._eval_bool(JS_HEADER_SHOWS_2ND_OR_3RD)

    async def _is_first_degree_connection(self) -> bool:
        if await self._header_shows_2nd_or_3rd_degree():
            return False
        if await self._has_any_selector(FIRST_DEGREE_SELECTORS):
            return True
        return await self._eval_bool(JS_TEXT_INDICATES_1ST_DEGREE)

    async def _has_connect_in_header_js(self) -> bool:
        return await self._eval_bool(
            """
(() => {
  const isVis = el => {
    if (!el) return false;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  for (const el of document.querySelectorAll('main button, main a, main div[role="button"]')) {
    if (!isVis(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.top > 650) continue;
    const text = (el.textContent || '').trim().toLowerCase();
    const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
    if (text === 'connect' || (aria.includes('invite') && aria.includes('connect'))) return true;
  }
  return false;
})()
"""
        )

    async def _js_click_connect_in_header(self) -> bool:
        return await self._eval_bool(
            """
(() => {
  const isVis = el => {
    if (!el) return false;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  for (const el of document.querySelectorAll('main button, main a, main div[role="button"]')) {
    if (!isVis(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.top > 650) continue;
    const text = (el.textContent || '').trim().toLowerCase();
    const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
    if (text === 'connect' || (aria.includes('invite') && aria.includes('connect'))) {
      el.click();
      return true;
    }
  }
  return false;
})()
"""
        )

    async def _js_click_profile_more_button(self) -> bool:
        return await self._eval_bool(
            """
(() => {
  const isVis = el => {
    if (!el) return false;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  for (const btn of document.querySelectorAll('main button')) {
    if (!isVis(btn)) continue;
    const r = btn.getBoundingClientRect();
    if (r.top > 650) continue;
    const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
    const text = (btn.textContent || '').trim().toLowerCase();
    if (aria.includes('more actions') || text === '...' || text === 'more') {
      btn.click();
      return true;
    }
  }
  return false;
})()
"""
        )

    async def _click_connect_in_open_menu(self) -> bool:
        return await self._eval_bool(
            """
(() => {
  const isVis = el => {
    if (!el) return false;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  for (const menu of document.querySelectorAll('.artdeco-dropdown__content, div[role="menu"]')) {
    if (!isVis(menu)) continue;
    for (const el of menu.querySelectorAll('div[role="button"], button, [role="menuitem"]')) {
      if (!isVis(el)) continue;
      const text = (el.textContent || '').trim().toLowerCase();
      const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
      if (text === 'connect' || (aria.includes('invite') && aria.includes('connect'))) {
        el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
        el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
        el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        return true;
      }
    }
  }
  return false;
})()
"""
        )

    @staticmethod
    def _unwrap_eval_payload(value: Any) -> Any:
        raw = value
        for _ in range(3):
            if isinstance(raw, dict) and "result" in raw:
                raw = raw["result"]
            else:
                break
        return raw

    async def _evaluate_unwrapped(self, expression: str) -> Any:
        raw = await self.browser.evaluate(expression)
        return self._unwrap_eval_payload(raw)

    async def _eval_bool(self, expression: str) -> bool:
        try:
            return bool(await self._evaluate_unwrapped(expression))
        except Exception:
            return False
