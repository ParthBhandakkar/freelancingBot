import json
import logging
import os
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
DEEP_ANALYSIS_TIMEOUT = 120


async def check_ollama_running() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            return resp.status_code == 200
    except Exception as e:
        logger.warning("OLLAMA not reachable: %s", e)
        return False


async def fetch_website_text(url: str, max_chars: int = 8000) -> str:
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            return text[:max_chars]
    except Exception as e:
        logger.warning("Failed to fetch website %s: %s", url, e)
        return ""


def build_deep_analysis_prompt(lead: dict, website_text: str, social_context: str) -> str:
    return f"""You are a sales intelligence analyst. Analyze this business and recommend services I can offer them as a freelance web developer/designer. Rank each recommendation by likelihood of acceptance (highest first).

BUSINESS INFO:
- Name: {lead.get('business_name', 'N/A')}
- Contact: {lead.get('name', 'N/A')}
- City: {lead.get('city', 'N/A')}
- Niche: {lead.get('niche', 'N/A')}
- Website: {lead.get('website_url', 'N/A')}
- Current online presence score: {lead.get('online_presence_score', 'N/A')}/100
- Lead score: {lead.get('lead_score', 'N/A')}/100

WEBSITE CONTENT:
{website_text[:6000]}

SOCIAL MEDIA / OTHER CONTEXT:
{social_context[:2000]}

INSTRUCTIONS:
1. Analyze their current online presence thoroughly (website quality, tech stack, social media, SEO, mobile friendliness, branding).
2. Identify specific pain points and opportunities.
3. Recommend services I can offer, ranked by likelihood the business would accept.
4. For each recommendation, provide:
   - service name
   - rank (1 = most likely to be accepted)
   - confidence score (0-100)
   - reasoning explaining why this is relevant and likely to be accepted
5. Also provide a brief summary of the overall analysis.

Respond ONLY with a valid JSON object (no markdown, no code fences):
{{
  "recommendations": [
    {{
      "service": "string",
      "rank": 1,
      "confidence": 95,
      "reasoning": "string"
    }}
  ],
  "analysis_summary": "string",
  "pain_points": ["string"],
  "opportunities": ["string"]
}}"""


async def run_deep_analysis(lead_data: dict, website_text: str, social_context: str) -> dict:
    prompt = build_deep_analysis_prompt(lead_data, website_text, social_context)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    try:
        async with httpx.AsyncClient(timeout=DEEP_ANALYSIS_TIMEOUT) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
            if resp.status_code != 200:
                text = await resp.aread()
                logger.error("OLLAMA returned %s: %s", resp.status_code, text.decode())
                return {"error": f"OLLAMA returned status {resp.status_code}", "recommendations": []}
            data = resp.json()
            raw = data.get("response", "")
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("OLLAMA response not valid JSON, raw: %s", raw[:200])
                result = {"recommendations": [], "analysis_summary": raw[:1000], "pain_points": [], "opportunities": []}
            return result
    except httpx.TimeoutException:
        logger.error("OLLAMA timed out after %ss", DEEP_ANALYSIS_TIMEOUT)
        return {"error": "OLLAMA request timed out", "recommendations": []}
    except Exception as e:
        logger.error("OLLAMA request failed: %s", e)
        return {"error": str(e), "recommendations": []}
