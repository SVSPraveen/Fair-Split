import os
import io
import base64
import logging
from typing import Optional, List, Dict, Any, Tuple
from dotenv import load_dotenv
import httpx
from google import genai
from google.genai import types
from google.genai.errors import APIError
import groq
from groq import Groq
import openai
from openai import OpenAI
from PIL import Image

load_dotenv()

logger = logging.getLogger(__name__)

# Locked Model IDs
GEMINI_VISION_PRIMARY = os.getenv("GEMINI_VISION_MODEL", "gemini-3.7-flash")
GROQ_TEXT_PRIMARY = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
OPENROUTER_VISION_FALLBACK = os.getenv("OPENROUTER_VISION_MODEL", "google/gemma-4-26b-a4b-it:free")
OPENROUTER_TEXT_FALLBACK = os.getenv("OPENROUTER_TEXT_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

# Hard Timeouts (15s for vision, 10s for text)
VISION_TIMEOUT_SECONDS: float = float(os.getenv("VISION_TIMEOUT_SECONDS", "15.0"))
TEXT_TIMEOUT_SECONDS: float = float(os.getenv("TEXT_TIMEOUT_SECONDS", "10.0"))


def _optimize_image_for_ocr(image_bytes: bytes, max_dimension: int = 800) -> bytes:
    """Resizes and compresses images to reduce token counts (~1000 tokens) and prevent TPM limits."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / float(max(w, h))
            new_size = (int(w * scale), int(h * scale))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()
    except Exception:
        return image_bytes


class LLMProvider:
    """LLM Provider abstraction handling primary and fallback routing for vision and text."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        groq_api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
    ):
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")

        # Clients
        self._gemini_client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        self._groq_client = (
            Groq(
                api_key=self.groq_key,
                timeout=TEXT_TIMEOUT_SECONDS,
                max_retries=0
            )
            if self.groq_key
            else None
        )
        self._openrouter_client = (
            OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_key,
                timeout=VISION_TIMEOUT_SECONDS,
                max_retries=0
            )
            if self.openrouter_key
            else None
        )

    def generate_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        force_fallback: bool = False,
        timeout_seconds: float = VISION_TIMEOUT_SECONDS
    ) -> str:
        text, _, _ = self.generate_vision_with_status(prompt, image_bytes, force_fallback, timeout_seconds)
        return text

    def generate_vision_with_status(
        self,
        prompt: str,
        image_bytes: bytes,
        force_fallback: bool = False,
        timeout_seconds: float = VISION_TIMEOUT_SECONDS
    ) -> Tuple[str, bool, Optional[str]]:
        """Executes a vision request using primary Gemini Flash, falling back to Groq Vision or OpenRouter.
        Returns: (response_text, used_fallback_boolean, fallback_reason)
        """
        # Optimize image to keep token usage small and prevent TPM rate limits
        optimized_bytes = _optimize_image_for_ocr(image_bytes, max_dimension=800)

        used_fallback = False
        fallback_reason = None

        # Try Primary Vision: Gemini 3.7 Flash
        if not force_fallback and self._gemini_client:
            try:
                img = Image.open(io.BytesIO(optimized_bytes))
                response = self._gemini_client.models.generate_content(
                    model=GEMINI_VISION_PRIMARY,
                    contents=[img, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=2048,
                        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
                    )
                )
                if response.text:
                    return response.text, False, None
                raise ValueError("Gemini returned empty response text")
            except Exception as e:
                err_str = str(e).lower()
                is_timeout = (
                    isinstance(e, (httpx.TimeoutException, TimeoutError))
                    or "timeout" in err_str
                    or "timed out" in err_str
                    or "deadline" in err_str
                )
                is_rate_limit = (
                    "429" in err_str
                    or "resourceexhausted" in err_str
                    or "quota" in err_str
                    or "rate limit" in err_str
                )
                if is_timeout:
                    fallback_reason = "timeout"
                    logger.warning(f"Gemini vision timed out after {int(timeout_seconds)}s, falling back.")
                elif is_rate_limit:
                    fallback_reason = "rate_limit_429"
                    logger.warning(f"Gemini vision returned 429, falling back to Groq / OpenRouter.")
                else:
                    fallback_reason = "error"
                    logger.warning(f"Gemini vision call failed ({e}). Attempting fallback.")

        # Fallback Vision: Try Groq Vision first (qwen/qwen3.6-27b), then OpenRouter
        used_fallback = True
        if fallback_reason is None:
            fallback_reason = "forced_fallback" if force_fallback else "primary_unavailable"

        base64_image = base64.b64encode(optimized_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{base64_image}"

        # 1. Try Groq Vision (qwen/qwen3.6-27b)
        if self._groq_client:
            try:
                resp = self._groq_client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": data_uri}}
                            ]
                        }
                    ],
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=timeout_seconds
                )
                if resp.choices and resp.choices[0].message.content:
                    return resp.choices[0].message.content, used_fallback, fallback_reason
            except (httpx.TimeoutException, groq.APITimeoutError, TimeoutError) as groq_to_err:
                logger.warning(f"Groq vision fallback timed out: {groq_to_err}")
                if not self._openrouter_client:
                    raise TimeoutError(f"Vision extraction timed out after {int(timeout_seconds)}s on Groq (qwen/qwen3.6-27b).") from groq_to_err
            except Exception as groq_err:
                logger.warning(f"Groq vision call failed ({groq_err}), falling back to OpenRouter.")

        # 2. Try OpenRouter Vision
        if not self._openrouter_client:
            raise ValueError("No fallback vision client available (both Groq and OpenRouter unavailable).")

        try:
            resp = self._openrouter_client.chat.completions.create(
                model=OPENROUTER_VISION_FALLBACK,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_uri}}
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=2048,
                timeout=timeout_seconds
            )
            return resp.choices[0].message.content or "", used_fallback, fallback_reason
        except (httpx.TimeoutException, openai.APITimeoutError, TimeoutError) as fb_err:
            logger.error(f"OpenRouter vision fallback timed out after {int(timeout_seconds)}s: {fb_err}")
            raise TimeoutError(
                f"Vision extraction timed out after {int(timeout_seconds)}s on fallback OpenRouter ({OPENROUTER_VISION_FALLBACK})."
            ) from fb_err

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        force_fallback: bool = False,
        timeout_seconds: float = TEXT_TIMEOUT_SECONDS
    ) -> str:
        text, _, _ = self.generate_text_with_status(prompt, system_prompt, force_fallback, timeout_seconds)
        return text

    def generate_text_with_status(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        force_fallback: bool = False,
        timeout_seconds: float = TEXT_TIMEOUT_SECONDS
    ) -> Tuple[str, bool, Optional[str]]:
        """Executes a text request using primary Groq, falling back to OpenRouter on 429 or timeout.
        Returns: (response_text, used_fallback_boolean, fallback_reason)
        """
        used_fallback = False
        fallback_reason = None

        if not force_fallback and self._groq_client:
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = self._groq_client.chat.completions.create(
                    model=GROQ_TEXT_PRIMARY,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=2048,
                    timeout=timeout_seconds
                )
                return response.choices[0].message.content or "", False, None
            except Exception as e:
                err_str = str(e).lower()
                is_timeout = (
                    isinstance(e, (httpx.TimeoutException, groq.APITimeoutError, TimeoutError))
                    or "timeout" in err_str
                    or "timed out" in err_str
                )
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str
                if is_timeout:
                    fallback_reason = "timeout"
                    logger.warning(f"Groq text timed out after {int(timeout_seconds)}s, falling back to OpenRouter.")
                elif is_rate_limit:
                    fallback_reason = "rate_limit_429"
                    logger.warning(f"Groq text returned 429, falling back to OpenRouter.")
                else:
                    fallback_reason = "error"
                    logger.warning(f"Groq text call failed ({e}). Attempting OpenRouter fallback.")

        # Fallback to OpenRouter Free Text
        used_fallback = True
        if fallback_reason is None:
            fallback_reason = "forced_fallback" if force_fallback else "primary_unavailable"

        if not self._openrouter_client:
            raise ValueError("OpenRouter client not initialized. Cannot perform text fallback.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = self._openrouter_client.chat.completions.create(
                model=OPENROUTER_TEXT_FALLBACK,
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
                timeout=timeout_seconds
            )
            return resp.choices[0].message.content or "", used_fallback, fallback_reason
        except (httpx.TimeoutException, openai.APITimeoutError, TimeoutError) as fb_err:
            logger.error(f"OpenRouter text fallback timed out after {int(timeout_seconds)}s: {fb_err}")
            raise TimeoutError(
                f"Description parsing timed out after {int(timeout_seconds)}s on fallback OpenRouter ({OPENROUTER_TEXT_FALLBACK})."
            ) from fb_err


_default_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _default_provider
    if _default_provider is None:
        _default_provider = LLMProvider()
    return _default_provider


def get_vision_client() -> LLMProvider:
    """Returns the LLM provider configured with Gemini Flash primary and OpenRouter fallback."""
    return get_llm_provider()


def get_text_client() -> LLMProvider:
    """Returns the LLM provider configured with Groq primary and OpenRouter fallback."""
    return get_llm_provider()

