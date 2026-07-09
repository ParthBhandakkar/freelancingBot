# LeadFinder — Improvement Plan & Strategy Guide

> Written after a full codebase review on 2026-07-06. This document explains **what the project is**, **what was broken**, **what is being built**, and **the realistic strategy** for landing 1–2 clients per month with it.

---

## 1. What This Project Is

**LeadFinder** is your personal lead-generation CRM for freelance web development work. The stack:

- **Backend:** FastAPI + SQLite + SQLAlchemy (`backend/`)
- **Frontend:** React 19 + Vite + Tailwind CSS 4 (`frontend/`)

The intended workflow:

1. **Find** local businesses by city/niche via Google Places API (Yelp fallback)
2. **Score** them on "lead potential" — no website = hot lead, established reviews = worth pursuing
3. **Analyze** their online presence — tech stack, SEO issues, social links, competitors
4. **Reach out** with templated emails (Gmail SMTP), call scripts, and follow-up sequences
5. **Track** everything on a dashboard; export to Google Sheets

The concept is solid: it's a mini Apollo/Instantly tuned specifically for *"local businesses with bad or missing websites"* — exactly the right niche for a freelancer selling web development.

---

## 2. Critical Bugs Found (and why they mattered)

Your database told the real story: **40 leads, all status "new", zero contacted, and zero had a website, phone, or email.** That wasn't a usage problem — it was three bugs:

### Bug 1 — Google Places enrichment was completely dead (critical)

**Where:** `backend/app/services/lead_finder.py`

**What:** The `httpx.AsyncClient` was created inside an `async with` block, but the loop that fetched each business's **website and phone number** (the Place Details call) ran *after* that block closed. Every details request threw `"Cannot send a request, as the client has been closed"`, which was silently swallowed by a bare `except: pass`.

**Impact:** Every imported lead had no website and no phone. Worse, the scoring logic then gave *every* lead "+35 points: No website (hot lead)" — so the scores were lies. You couldn't email, call, or analyze anyone.

**Fix:** Move the details-fetch loop inside the client's lifetime. ✅ Fixed.

### Bug 2 — Outgoing emails were signed "Your Name" (embarrassing)

**Where:** `backend/app/routes/outreach.py` (two places)

**What:** The template variables `my_name` and `my_company` were hardcoded to the literal strings `"Your Name"` and `"Your Company"` — even though `SMTP_FROM_NAME` existed in your `.env` and the variable help text claimed it was used. The same hardcoding existed in the frontend (`LeadDetail.jsx`).

**Impact:** Any cold email you sent ended with *"Best, Your Name"*. One glance and the recipient deletes it — or worse, remembers you.

**Fix:** A proper **Settings** system (DB-backed, editable in the UI, seeded from `.env`) that every template render reads from. ✅ Being built.

### Bug 3 — No email addresses were ever captured (structural)

**What:** Google Places doesn't return email addresses — ever. The existing "contact enricher" only *guessed* patterns (`info@domain.com`) and Hunter.io wasn't configured (its free tier is only 25 requests/month anyway).

**Impact:** The entire email-outreach system had nobody to email. 0 of 40 leads had an address.

**Fix:** A real **email scraper** that crawls each lead's website (homepage + `/contact`, `/about` pages) for `mailto:` links and email patterns, filters out junk (sentry.io, noreply@, image filenames), and ranks own-domain emails first. This is free, legal, and finds addresses for most small businesses that have websites. ✅ Being built.

### Also worth knowing (security)

Your live `.env`, `service-account.json`, and the `delta-avenue-*.json` Google credential sit in the project folder. `.gitignore` covers them, but **this isn't a git repo yet** — double-check those files are ignored before you ever push this anywhere public.

---

## 3. The Realistic Math: What 1–2 Clients/Month Actually Takes

**Honesty first: no tool guarantees clients.** But the funnel for local web-dev freelancing is well understood:

| Stage | Typical rate |
|---|---|
| Cold email reply rate (generic template) | 2–5% |
| Cold email reply rate (personalized + something of value attached) | 8–15% |
| Cold call to no-website business → conversation | 10–20% |
| Conversations → closed client | 10–20% |

Working backwards from **1–2 clients/month**:

- You need **~10–20 real conversations/month**
- Which means **~150–300 generic touches**, or — much better — **~60–100 genuinely personalized ones**
- Which means **3–5 quality touches per working day**

**The tool's real job** is making those 3–5 quality daily touches take 20 minutes instead of 2 hours. That's what everything below is designed around.

### The key strategic insight: match the channel to the lead

Your "hottest" leads — businesses with **no website** — by definition **have no email to find**. A no-website bakery is reached by **phone** or **Instagram/Facebook DM**, not email. So the tool now segments every lead into a channel automatically:

| Lead situation | Channel | How you reach them |
|---|---|---|
| Has a (bad) website → email found on it | 📧 **Email** | Personalized email + audit report |
| No website, has phone | 📞 **Call** | Call script (already in the tool) |
| No website, has social profiles | 💬 **DM** | Copy-paste Instagram/Facebook message |
| Nothing found yet | 🔍 **Research** | Needs manual digging or skip |

Cold calls to no-website businesses convert better than any email for this exact offer — lean into that queue.

### Non-code advice that matters more than any feature

1. **Niche down.** Pick 2–3 niches (e.g. dentists, salons, restaurants) and one metro area. Your portfolio, templates, and audit reports all get sharper, and referrals compound within a niche.
2. **Have a portfolio page** at the domain you send email from. The first thing a business owner does with a cold email is look *you* up. No website for the web developer = instant delete.
3. **Low volume, high quality.** 20–30 emails/day max from Gmail protects deliverability, and at your scale personalization beats volume anyway.
4. **Follow up.** 50–60% of replies come from follow-ups #2–4 — exactly the ones humans forget to send. The tool now automates them.

---

## 4. What's Being Built (Feature by Feature)

### Phase 1 — Make it functional

| # | Feature | Why |
|---|---|---|
| 1.1 | **Fix the closed-client bug** in `lead_finder.py` | Websites + phones actually populate on import |
| 1.2 | **Email scraper service** (`email_scraper.py`) | Crawls lead websites for real contact emails — unblocks the entire outreach system |
| 1.3 | **Settings system** (DB table + API + UI page) | Your name, company, signature, Calendly link, daily send limit — no more "Your Name" emails, no more editing `.env` |
| 1.4 | **Re-enrich existing leads** | The 40 broken leads get websites/phones/emails backfilled |

### Phase 2 — Channel segmentation

| # | Feature | Why |
|---|---|---|
| 2.1 | **`channel` column** on every lead (email/call/dm/research) | Computed automatically from what contact info + social profiles exist |
| 2.2 | **Channel badges** throughout the UI | You always know *how* to reach a lead at a glance |
| 2.3 | **Call queue & DM queue** on the Today page | No-website leads stop being dead ends |

### Phase 3 — The conversion multiplier: send proof, not promises

| # | Feature | Why |
|---|---|---|
| 3.1 | **Audit report generator** | One-click generates a polished, branded HTML audit report for a lead (their score, specific issues, competitor comparison, what to fix). Print-to-PDF ready. *"I already made this for you"* out-converts *"I noticed some issues"* by a lot. Uses the `asset_generated`/`asset_url` fields that already existed in your schema but had nothing behind them. |
| 3.2 | **Claude AI integration** (`ai_service.py`) | Personalized email drafting from the lead's actual analysis data (their tech stack, their specific issues, their competitors). Template emails read like spam; AI-personalized ones get replies. Also writes the audit report narrative. Falls back to templates if no API key is set. |

### Phase 4 — Automation

| # | Feature | Why |
|---|---|---|
| 4.1 | **Auto follow-up scheduler** (APScheduler) | Checks due sequence steps daily and sends them — respecting your daily send limit. Sequences existed before but required manually clicking "advance". |
| 4.2 | **One-click Import + Analyze + Draft** | Old flow: search → import → open lead → run analysis → pick template → fill → send (6+ steps). New flow: one button does import, email scrape, full analysis, channel detection, and pre-drafts the outreach. |
| 4.3 | **Today queue endpoint** | One API call returns: follow-ups due today, hot new leads to contact (grouped by channel), and leads awaiting reply check. |

---

## 5. UI/UX Overhaul

The old UI was organized around *data* (tables, charts). The new UI is organized around *your daily work*:

| Change | Explanation |
|---|---|
| **"Today" page — new home screen** | Opens to: follow-ups due, leads to contact today by channel (email/call/DM), replies to log. You open the app and it tells you what to do. Zero decisions needed. |
| **Pipeline (kanban) view** | New → Contacted → Qualified → Converted / Lost as drag-and-drop columns. The statuses already existed in the data model; now you can see and move deals visually. |
| **Settings page** | Edit your identity (name, company, signature, Calendly), sending behavior (daily limit, auto-send toggle), and see which API keys are configured — all without touching `.env`. |
| **Toasts instead of `alert()`** | The old UI used browser `alert()` popups everywhere. Replaced with non-blocking toast notifications. |
| **Bulk actions on Leads table** | Select multiple leads → bulk delete / bulk status change. |
| **Channel badges everywhere** | Search results, lead lists, lead detail — every lead shows 📧/📞/💬/🔍. |
| **AI Draft + Audit buttons on Lead Detail** | Generate a personalized email or a full audit report in one click from the lead's page. |
| **Email preview before send** | You always see and can edit exactly what goes out. |

---

## 6. Setup: Keys You Need (added to `.env`)

| Key | Required? | Where to get it | Free tier |
|---|---|---|---|
| `GOOGLE_API_KEY` | ✅ Already set | [console.cloud.google.com](https://console.cloud.google.com) → enable **Places API** | $200/mo credit ≈ thousands of searches |
| `ANTHROPIC_API_KEY` | ⭐ Strongly recommended | [platform.claude.com](https://platform.claude.com) → API Keys | Pay-as-you-go; a personalized email draft costs ~$0.01–0.05 |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | ✅ Already set | Gmail → Manage Account → Security → 2-Step Verification → **App Passwords** | Free (≈500 emails/day cap — stay well under) |
| `MY_NAME`, `MY_COMPANY`, `MY_WEBSITE`, `CALENDLY_LINK` | ✅ Fill these in | You :) — these seed the Settings page and go into every email | — |
| `YELP_API_KEY` | Optional | [yelp.com/developers](https://www.yelp.com/developers) → Fusion API | 500 calls/day |
| `HUNTER_API_KEY` | Optional | [hunter.io](https://hunter.io) → API | 25 searches/mo (the built-in scraper usually makes this unnecessary) |

**Steps for the Anthropic key (the one new one that matters):**
1. Go to [platform.claude.com](https://platform.claude.com) and sign up / log in
2. Add a payment method (Settings → Billing) — $5–10 of credit lasts a long time at this usage level
3. Create an API key (Settings → API Keys → Create Key)
4. Paste it into `backend/.env` as `ANTHROPIC_API_KEY=sk-ant-...`
5. Restart the backend — the AI Draft and Audit features light up automatically (everything still works without it, just with templates instead of AI personalization)

---

## 7. Your Daily Operating Routine (20–30 min/day)

Once this build is done, the routine that gets you to 1–2 clients/month:

1. **Open the app → Today page.** It shows follow-ups due and new leads to touch.
2. **Send the due follow-ups** (or let auto-send do it — check the log).
3. **Work the email queue:** 3–5 leads → click AI Draft → skim/tweak → attach audit link → send.
4. **Work the call queue:** 2–3 no-website leads → use the call script → log the outcome (one click: status → contacted).
5. **Work the DM queue:** 2–3 leads with Instagram/Facebook → copy the DM message → send from your phone.
6. **Log replies:** anyone who answered → status "Qualified" → book them on your Calendly.
7. **Weekly (Sunday, 30 min):** run 2–3 searches in your niche/city, one-click Import+Analyze the best 20–30, so Monday's queue is full.

That's ~25 quality touches/day across three channels ≈ 500/month ≈ 15–25 conversations ≈ **1–3 clients** at typical close rates. Realistic, not guaranteed — but the funnel math works if the inputs happen daily.

---

## 8. What Was NOT Built (deliberately) and Future Ideas

- **Reply detection via IMAP** — reading your Gmail inbox to auto-mark replies. Doable, but adds OAuth complexity; for now logging replies is one click on the Today page. Good v2 feature.
- **Demo homepage mockup generator** — auto-building a preview site per lead. Extremely high conversion but heavier build; the audit report covers 80% of the value. Good v2.
- **Open/click tracking pixels** — hurts deliverability at small scale and adds infra. Skip until volume justifies it.
- **Multi-mailbox rotation / warmup** — only needed past ~50 emails/day. You're not there yet, and personal-scale sending is actually an advantage.
