"""LinkedIn profile header heuristics used by outreach flows."""

_PM = "main"

PENDING_INVITE_SELECTORS: list[str] = [
    f"{_PM} button:has-text('Pending')",
    f"{_PM} button[aria-label*='Pending']",
    f"{_PM} button[aria-label*='pending']",
    f"{_PM} a:has-text('Pending')",
    f"{_PM} div[role='button']:has-text('Pending')",
    f"{_PM} span.artdeco-button__text:has-text('Pending')",
]

JS_PENDING_IN_HEADER = """
(() => {
  const main = document.querySelector('main');
  if (!main) return false;
  const top = main.getBoundingClientRect().top;
  const cutoff = top + 420;
  const nodes = main.querySelectorAll(
    'button, a[href], div[role="button"], span.artdeco-button__text'
  );
  for (const el of nodes) {
    const r = el.getBoundingClientRect();
    if (r.bottom < top || r.top > cutoff || r.width < 2 || r.height < 2) continue;
    const t = (el.textContent || '').trim().toLowerCase();
    if (t !== 'pending' && !/^pending\\b/.test(t)) continue;
    const s = window.getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') continue;
    if (parseFloat(s.opacity || '1') < 0.05) continue;
    return true;
  }
  return false;
})()
"""

JS_HEADER_SHOWS_2ND_OR_3RD = """
(() => {
  const main = document.querySelector('main');
  if (!main) return false;
  const text = (main.innerText || '').slice(0, 1000).toLowerCase();
  if (text.includes('2nd degree connection')) return true;
  if (text.includes('3rd degree connection')) return true;
  if (/\\u00b7\\s*2nd\\b/.test(text)) return true;
  if (/\\u00b7\\s*3rd\\b/.test(text)) return true;
  if (/\\b2nd\\b/.test(text.slice(0, 500))) return true;
  if (/\\b3rd\\b/.test(text.slice(0, 500))) return true;
  return false;
})()
"""

JS_TEXT_INDICATES_1ST_DEGREE = """
(() => {
  const main = document.querySelector('main');
  if (!main) return false;
  const text = (main.innerText || '').slice(0, 1500).toLowerCase();
  if (text.includes('1st degree connection')) return true;
  if (/\\u00b7\\s*1st\\b/.test(text.slice(0, 700))) return true;
  return false;
})()
"""
