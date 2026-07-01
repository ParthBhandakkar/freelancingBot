import re

INTENT_KEYWORDS = {
    "high": [
        "need website", "website needed", "need a website", "need new website",
        "website redesign", "redesign website", "outdated website",
        "update website", "rebuild website", "no website",
        "need social media", "need marketing", "need seo",
        "need online presence", "not online", "hard to find online",
        "bad website", "terrible website", "ugly website",
        "old website", "dated website", "not mobile friendly",
        "not showing up", "no google", "can't find",
        "looking for web designer", "need help with",
    ],
    "medium": [
        "new business", "just opened", "recently opened",
        "growing", "expanding", "launching",
        "small business", "local business", "startup",
        "needs improvement", "could be better",
        "wish they had", "should get", "should have",
    ],
    "low": [
        "website ok", "good enough", "works fine",
        "satisfied", "happy with",
    ],
}

NEGATIVE_SIGNALS = [
    "doesn't have a website", "don't have a website",
    "no website yet", "isn't online", "aren't online",
    "not digital", "not tech savvy",
]


def score_keywords(text: str) -> dict:
    if not text:
        return {"score": 0, "signals": [], "category": "unknown"}

    text_lower = text.lower()
    signals = []
    for level, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                signals.append({"keyword": kw, "level": level})

    has_negative = any(sig in text_lower for sig in NEGATIVE_SIGNALS)

    if has_negative:
        signals.append({"keyword": "no_website_detected", "level": "high"})

    if not signals:
        return {"score": 0, "signals": [], "category": "unknown"}

    weights = {"high": 30, "medium": 15, "low": -10}
    score = sum(weights[s["level"]] for s in signals)
    score = max(0, min(100, score))

    return {"score": score, "signals": signals, "category": "strong" if score >= 50 else "moderate" if score >= 20 else "weak"}
