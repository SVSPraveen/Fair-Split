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
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

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


import re
import time


def validate_image_bytes(image_bytes: bytes) -> None:
    """Pre-flight checks before sending image to OCR pipeline.
    
    Raises ValueError with a user-friendly message on:
    - File too large (>20MB)
    - HEIC/HEIF format (not supported without extra lib)
    - Completely unreadable bytes (not a valid image)
    """
    # 1. Size guard — prevent memory exhaustion from huge RAW/DSLR photos
    max_bytes = 20 * 1024 * 1024  # 20 MB
    if len(image_bytes) > max_bytes:
        raise ValueError(
            f"Image file is too large ({len(image_bytes) / 1_048_576:.1f} MB). "
            "Please upload a photo under 20 MB. Tip: screenshot the receipt instead of uploading a RAW file."
        )

    # 2. HEIC/HEIF detection — first 12 bytes contain 'heic' or 'heif' or 'mif1' or 'msf1'
    header = image_bytes[:16].lower()
    if any(sig in header for sig in [b'heic', b'heif', b'mif1', b'msf1']):
        raise ValueError(
            "HEIC/HEIF format (iPhone default) is not supported. "
            "Please convert to JPEG or PNG: on iPhone, go to Settings → Camera → Formats → Most Compatible."
        )

    # 3. Attempt to open — catches completely corrupted/truncated files
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()  # Verifies without decoding the full image
    except Exception as e:
        raise ValueError(
            f"The uploaded file could not be read as an image ({type(e).__name__}). "
            "Please try re-saving or re-exporting the receipt photo and upload again."
        )


def _optimize_image_for_ocr(image_bytes: bytes, max_dimension: int = 640) -> bytes:
    """Prepares an image for OCR:
    - Applies EXIF orientation correction (fixes sideways phone photos)
    - Converts RGBA/P/grayscale to RGB
    - Auto-levels exposure (ImageOps.autocontrast) to handle faded/overexposed receipts
    - Applies a gentle unsharp-mask to bring out faded ink on torn/tape-repaired paper
    - Boosts contrast by 1.35x so dim thermal prints are legible
    - Resizes to max_dimension keeping aspect ratio (LANCZOS)
    - Saves as JPEG quality=78 — enough clarity for OCR, small enough to stay under Groq TPM
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))

        # Fix EXIF orientation — phone cameras store portrait shots as landscape
        # with an EXIF rotation tag that most apps auto-apply on display.
        # PIL does NOT auto-rotate, so we must do it explicitly.
        img = ImageOps.exif_transpose(img)

        # Convert palette / transparency / grayscale modes to RGB
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")
        elif img.mode not in ("RGB", "CMYK"):
            img = img.convert("RGB")

        # Auto-level: stretches the histogram so overexposed or underexposed
        # receipts (e.g. very white thermal paper or dark phone-camera shots) normalize
        img = ImageOps.autocontrast(img, cutoff=1)

        # Unsharp mask — sharpens faded or slightly out-of-focus text without noise
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))

        # Contrast boost — makes low-contrast thermal printer ink stand out
        img = ImageEnhance.Contrast(img).enhance(1.35)

        # Resize to max_dimension if larger
        w, h = img.size
        if max(w, h) > max_dimension:
            scale = max_dimension / float(max(w, h))
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=78, optimize=True)
        result = out.getvalue()

        # Sanity check: output should be a valid JPEG (starts with FF D8)
        if len(result) < 100 or result[:2] != b'\xff\xd8':
            logger.warning("Preprocessed image failed JPEG sanity check; falling back to original bytes")
            return image_bytes

        return result
    except Exception as e:
        logger.warning(f"Image preprocessing failed ({type(e).__name__}: {e}); using original bytes")
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
        """Executes a vision request using optimal preference order:
        1. Primary: Groq Vision (qwen/qwen3.6-27b with token-optimized image)
        2. Tier 2: Gemini 3.7 Flash
        3. Tier 3: OpenRouter Vision (gemma-4-26b-a4b-it:free)

        Returns: (response_text, used_fallback_boolean, fallback_reason)
        """
        # Optimize image to keep token usage small (~1000 tokens) and prevent TPM limits
        optimized_bytes = _optimize_image_for_ocr(image_bytes, max_dimension=800)
        base64_image = base64.b64encode(optimized_bytes).decode("utf-8")
        data_uri = f"data:image/jpeg;base64,{base64_image}"

        used_fallback = False
        fallback_reason = None

        # -------------------------------------------------------------
        # Tier 1 (Primary): Groq Vision (qwen/qwen3.6-27b)
        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # Tier 1 (Primary): Groq Vision (qwen/qwen3.6-27b)
        # -------------------------------------------------------------
        if not force_fallback and self._groq_client:
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    resp = self._groq_client.chat.completions.create(
                        model="qwen/qwen3.6-27b",
                        messages=[
                            {"role": "system", "content": "You are a specialized receipt OCR JSON engine. Output ONLY valid JSON conforming to the schema. Do not output preamble, thinking tags, or markdown commentary."},
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": data_uri}}
                                ]
                            }
                        ],
                        temperature=0.0,
                        max_tokens=4096,
                        timeout=timeout_seconds
                    )
                    if resp.choices and resp.choices[0].message.content:
                        return resp.choices[0].message.content, False, None
                    raise ValueError("Groq vision returned empty response")
                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = "429" in err_str or "quota" in err_str or "rate limit" in err_str
                    if is_rate_limit and attempt < max_retries:
                        match = re.search(r"try again in ([\d\.]+)s", err_str)
                        delay = float(match.group(1)) + 0.5 if match else (2.0 * (attempt + 1))
                        logger.warning(f"Groq vision 429 on attempt {attempt+1}. Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                        continue

                    is_timeout = (
                        isinstance(e, (httpx.TimeoutException, groq.APITimeoutError, TimeoutError))
                        or "timeout" in err_str
                        or "timed out" in err_str
                    )
                    if is_timeout:
                        fallback_reason = "timeout"
                        logger.warning(f"Groq vision timed out after {int(timeout_seconds)}s, falling back to Gemini.")
                    elif is_rate_limit:
                        fallback_reason = "rate_limit_429"
                        logger.warning(f"Groq vision returned 429, falling back to Gemini.")
                    else:
                        fallback_reason = "error"
                        logger.warning(f"Groq vision call failed ({e}). Falling back to Gemini.")
                    break

        # -------------------------------------------------------------
        # Tier 2 (Secondary): Gemini 3.7 Flash
        # -------------------------------------------------------------
        used_fallback = True
        if fallback_reason is None:
            fallback_reason = "forced_fallback" if force_fallback else "primary_unavailable"

        if self._gemini_client:
            try:
                img = Image.open(io.BytesIO(optimized_bytes))
                response = self._gemini_client.models.generate_content(
                    model=GEMINI_VISION_PRIMARY,
                    contents=[img, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=4096,
                        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
                    )
                )
                if response.text:
                    return response.text, used_fallback, fallback_reason
                raise ValueError("Gemini returned empty response text")
            except (httpx.TimeoutException, TimeoutError) as gemini_to_err:
                logger.warning(f"Gemini vision fallback timed out: {gemini_to_err}")
                if not self._openrouter_client:
                    raise TimeoutError(f"Vision extraction timed out after {int(timeout_seconds)}s on Gemini ({GEMINI_VISION_PRIMARY}).") from gemini_to_err
            except Exception as gemini_err:
                logger.warning(f"Gemini vision fallback failed ({gemini_err}), falling back to OpenRouter.")

        # -------------------------------------------------------------
        # Tier 3 (Tertiary): OpenRouter Vision (google/gemma-4-26b-a4b-it:free)
        # -------------------------------------------------------------
        if not self._openrouter_client:
            raise ValueError("No fallback vision client available (all providers exhausted).")

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
                max_tokens=4096,
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
            max_retries = 2
            for attempt in range(max_retries + 1):
                try:
                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

                    response = self._groq_client.chat.completions.create(
                        model=GROQ_TEXT_PRIMARY,
                        messages=messages,
                        temperature=0.1,
                        max_tokens=4096,
                        timeout=timeout_seconds
                    )
                    return response.choices[0].message.content or "", False, None
                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str
                    if is_rate_limit and attempt < max_retries:
                        match = re.search(r"try again in ([\d\.]+)s", err_str)
                        delay = float(match.group(1)) + 0.5 if match else (2.0 * (attempt + 1))
                        logger.warning(f"Groq text 429 on attempt {attempt+1}. Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                        continue

                    is_timeout = (
                        isinstance(e, (httpx.TimeoutException, groq.APITimeoutError, TimeoutError))
                        or "timeout" in err_str
                        or "timed out" in err_str
                    )
                    if is_timeout:
                        fallback_reason = "timeout"
                        logger.warning(f"Groq text timed out after {int(timeout_seconds)}s, falling back to OpenRouter.")
                    elif is_rate_limit:
                        fallback_reason = "rate_limit_429"
                        logger.warning(f"Groq text returned 429, falling back to OpenRouter.")
                    else:
                        fallback_reason = "error"
                        logger.warning(f"Groq text call failed ({e}). Attempting fallback.")
                    break

        # Fallback Text: Try Gemini first, then OpenRouter
        used_fallback = True
        if fallback_reason is None:
            fallback_reason = "forced_fallback" if force_fallback else "primary_unavailable"

        # 1. Try Gemini Text
        if self._gemini_client:
            try:
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                response = self._gemini_client.models.generate_content(
                    model=GEMINI_VISION_PRIMARY,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=4096,
                        http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
                    )
                )
                if response.text:
                    return response.text, used_fallback, fallback_reason
            except (httpx.TimeoutException, TimeoutError) as gemini_to_err:
                logger.warning(f"Gemini text fallback timed out: {gemini_to_err}")
                if not self._openrouter_client:
                    raise TimeoutError(f"Description parsing timed out after {int(timeout_seconds)}s on Gemini ({GEMINI_VISION_PRIMARY}).") from gemini_to_err
            except Exception as gemini_err:
                logger.warning(f"Gemini text fallback failed ({gemini_err}), falling back to OpenRouter.")

        # 2. Try OpenRouter Text
        if not self._openrouter_client:
            raise ValueError("No fallback text client available (both Groq and OpenRouter unavailable).")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = self._openrouter_client.chat.completions.create(
                model=OPENROUTER_TEXT_FALLBACK,
                messages=messages,
                temperature=0.1,
                max_tokens=4096,
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

