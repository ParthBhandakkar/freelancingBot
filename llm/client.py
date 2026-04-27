"""
LLM Client — unified interface for Kimi K2.5, Ollama, and OpenAI-compatible APIs.

Uses the OpenAI SDK (which works with all three providers) so we can switch
between providers by changing the base URL and API key.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from loguru import logger
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

JSON_ONLY_INSTRUCTION = (
    "\n\nReturn valid JSON only. "
    "Do not wrap it in markdown fences. "
    "Do not add commentary before or after the JSON."
)


class LLMClient:
    """Async wrapper around the configured LLM provider."""

    @staticmethod
    def _preview_text(text: str, max_len: int = 420) -> str:
        compact = re.sub(r"\s+", " ", text or "").strip()
        if len(compact) <= max_len:
            return compact
        return compact[: max_len - 3] + "..."

    def _log_request(
        self,
        *,
        request_name: str | None,
        system_prompt: str,
        user_message: str,
        image_path: str | Path | None = None,
    ) -> str:
        name = request_name or "request"
        logger.info(
            "LLM[{}] prompt - system={} | user={}",
            name,
            self._preview_text(system_prompt, 180),
            self._preview_text(user_message, 420),
        )
        if image_path is not None:
            logger.info("LLM[{}] image - {}", name, Path(image_path).name)
        logger.debug("LLM[{}] full system prompt:\n{}", name, system_prompt)
        logger.debug("LLM[{}] full user prompt:\n{}", name, user_message)
        return name

    def _log_response(self, *, request_name: str, response_text: str) -> None:
        logger.info(
            "LLM[{}] answer - {}",
            request_name,
            self._preview_text(response_text, 520),
        )
        logger.debug("LLM[{}] full answer:\n{}", request_name, response_text)

    @staticmethod
    def _strip_markdown_fences(raw: str) -> str:
        cleaned = (raw or "").strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = [line for line in lines if not line.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        return cleaned

    def _parse_json_payload(self, raw: str, *, request_name: str) -> Any:
        cleaned = self._strip_markdown_fences(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "LLM[{}] invalid JSON on first parse - {}",
                request_name,
                self._preview_text(raw, 300),
            )

        candidates: list[str] = []
        first_obj = cleaned.find("{")
        last_obj = cleaned.rfind("}")
        if first_obj != -1 and last_obj > first_obj:
            candidates.append(cleaned[first_obj : last_obj + 1])

        first_arr = cleaned.find("[")
        last_arr = cleaned.rfind("]")
        if first_arr != -1 and last_arr > first_arr:
            candidates.append(cleaned[first_arr : last_arr + 1])

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        raise json.JSONDecodeError("Could not parse JSON payload", cleaned, 0)

    def __init__(self) -> None:
        self._availability_cache: bool | None = None
        self._availability_checked_at = 0.0
        provider = settings.llm_provider
        if provider == "kimi":
            self._client = AsyncOpenAI(
                api_key=settings.kimi_api_key,
                base_url=settings.kimi_base_url,
            )
            self._model = settings.kimi_model
        elif provider == "ollama":
            self._client = AsyncOpenAI(
                api_key="ollama",  # Ollama doesn't need a real key
                base_url=f"{settings.ollama_base_url}/v1",
            )
            self._model = settings.ollama_model
        elif provider == "openai":
            self._client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
            self._model = settings.openai_model
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

        logger.info("LLM client initialised — provider={}, model={}", provider, self._model)

    @staticmethod
    def _probe_http(url: str, timeout: float) -> bool:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=timeout) as response:
            return 200 <= getattr(response, "status", 200) < 500

    async def is_available(self, timeout: float = 1.5) -> bool:
        if self._availability_cache is True and (time.time() - self._availability_checked_at) < 30:
            return self._availability_cache

        provider = settings.llm_provider
        if provider == "ollama":
            available = await self._ollama_available(timeout)
        elif provider == "openai":
            available = bool(settings.openai_api_key.strip())
        else:
            available = bool(settings.kimi_api_key.strip())

        self._availability_cache = available
        self._availability_checked_at = time.time()
        if not available:
            logger.warning("LLM runtime unavailable for provider={}", provider)
        return available

    async def _ollama_available(self, timeout: float) -> bool:
        base_url = settings.ollama_base_url.rstrip("/")
        probe_urls = [
            f"{base_url}/api/tags",
            f"{base_url}/v1/models",
        ]
        if "localhost" in base_url:
            probe_urls.extend(
                [
                    f"{base_url.replace('localhost', '127.0.0.1')}/api/tags",
                    f"{base_url.replace('localhost', '127.0.0.1')}/v1/models",
                ]
            )

        for probe_url in dict.fromkeys(probe_urls):
            try:
                if await asyncio.to_thread(self._probe_http, probe_url, timeout):
                    return True
            except Exception:
                continue

        if await asyncio.to_thread(self._probe_ollama_process, timeout):
            return True

        return await asyncio.to_thread(self._probe_ollama_cli, timeout)

    @staticmethod
    def _probe_ollama_process(timeout: float) -> bool:
        try:
            process = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq ollama.exe"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(1.5, timeout),
                check=False,
                text=True,
            )
            return process.returncode == 0 and "ollama.exe" in (process.stdout or "").lower()
        except Exception:
            return False

    @staticmethod
    def _probe_ollama_cli(timeout: float) -> bool:
        try:
            process = subprocess.run(
                ["ollama", "list"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(2.0, timeout * 2),
                check=False,
                text=True,
                env=os.environ.copy(),
            )
            return process.returncode == 0
        except Exception:
            return False

    # ── Text completion ─────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        request_name: str | None = None,
    ) -> str:
        """Send a text chat message and return the assistant's reply."""
        logger.debug("LLM chat — system_prompt[:80]={!r}", system_prompt[:80])
        name = self._log_request(
            request_name=request_name,
            system_prompt=system_prompt,
            user_message=user_message,
        )
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = (response.choices[0].message.content or "").strip()
        self._log_response(request_name=name, response_text=text)
        return text

    # ── Vision (screenshot analysis) ────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def chat_with_image(
        self,
        system_prompt: str,
        user_message: str,
        image_path: str | Path,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        request_name: str | None = None,
    ) -> str:
        """Send a message with an image (screenshot) for visual analysis."""
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Screenshot not found: {image_path}")

        name = self._log_request(
            request_name=request_name,
            system_prompt=system_prompt,
            user_message=user_message,
            image_path=image_path,
        )
        img_bytes = image_path.read_bytes()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        mime = "image/png" if image_path.suffix == ".png" else "image/jpeg"

        logger.debug("LLM vision — image={}, size={:.0f}KB", image_path.name, len(img_bytes) / 1024)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_message},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}",
                            },
                        },
                    ],
                },
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = (response.choices[0].message.content or "").strip()
        self._log_response(request_name=name, response_text=text)
        return text

    # ── Structured JSON output ──────────────────────────────────────────
    async def chat_json(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        request_name: str | None = None,
    ) -> dict[str, Any]:
        """Send a chat and parse the reply as JSON."""
        raw = await self.chat(
            system_prompt=system_prompt + JSON_ONLY_INSTRUCTION,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
            request_name=request_name or "json_request",
        )
        parsed = self._parse_json_payload(raw, request_name=request_name or "json_request")
        if not isinstance(parsed, dict):
            raise TypeError(f"Expected JSON object, got {type(parsed).__name__}")
        return parsed
        if False:
            logger.warning("Failed to parse LLM JSON — raw[:300]={!r}", raw[:300])

    async def chat_json_with_image(
        self,
        system_prompt: str,
        user_message: str,
        image_path: str | Path,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        request_name: str | None = None,
    ) -> dict[str, Any]:
        """Send a message with image and parse reply as JSON."""
        raw = await self.chat_with_image(
            system_prompt=system_prompt + JSON_ONLY_INSTRUCTION,
            user_message=user_message,
            image_path=image_path,
            temperature=temperature,
            max_tokens=max_tokens,
            request_name=request_name or "json_vision_request",
        )
        parsed = self._parse_json_payload(raw, request_name=request_name or "json_vision_request")
        if not isinstance(parsed, dict):
            raise TypeError(f"Expected JSON object, got {type(parsed).__name__}")
        return parsed
        if False:
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM vision JSON — raw[:300]={!r}", raw[:300])
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
            raise


# Singleton
llm_client = LLMClient()
