import os
import io
import base64
import logging
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError
from groq import Groq
from openai import OpenAI
from PIL import Image

load_dotenv()

logger = logging.getLogger(__name__)

# Locked Model IDs
GEMINI_VISION_PRIMARY = os.getenv("GEMINI_VISION_MODEL", "gemini-3.7-flash")
GROQ_TEXT_PRIMARY = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-120b")
OPENROUTER_VISION_FALLBACK = os.getenv("OPENROUTER_VISION_MODEL", "google/gemma-4-26b-a4b-it:free")
OPENROUTER_TEXT_FALLBACK = os.getenv("OPENROUTER_TEXT_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")


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
        self._groq_client = Groq(api_key=self.groq_key) if self.groq_key else None
        self._openrouter_client = (
            OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_key
            )
            if self.openrouter_key
            else None
        )

    def generate_vision(
        self,
        prompt: str,
        image_bytes: bytes,
        force_fallback: bool = False
    ) -> str:
        """Executes a vision request using primary Gemini Flash, falling back to OpenRouter on 429."""
        if not force_fallback and self._gemini_client:
            try:
                pil_image = Image.open(io.BytesIO(image_bytes))
                response = self._gemini_client.models.generate_content(
                    model=GEMINI_VISION_PRIMARY,
                    contents=[pil_image, prompt]
                )
                if response.text:
                    return response.text
                raise ValueError("Gemini returned empty response text")
            except Exception as e:
                # Detect rate limit 429 or ResourceExhausted
                err_str = str(e).lower()
                is_rate_limit = (
                    "429" in err_str
                    or "resourceexhausted" in err_str
                    or "quota" in err_str
                    or "rate limit" in err_str
                )
                if not is_rate_limit:
                    # If not a rate limit error, propagate or try fallback if Gemini key was missing/invalid
                    logger.warning(f"Gemini vision call failed: {e}. Attempting OpenRouter fallback.")
                else:
                    logger.warning(f"Gemini vision rate limit hit (429): {e}. Falling back to OpenRouter ({OPENROUTER_VISION_FALLBACK}).")

        # Fallback to OpenRouter Free Vision
        if not self._openrouter_client:
            raise ValueError("OpenRouter client not initialized. Cannot perform vision fallback.")

        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_image}"

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
            max_tokens=2048
        )
        return resp.choices[0].message.content or ""

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        force_fallback: bool = False
    ) -> str:
        """Executes a text request using primary Groq, falling back to OpenRouter on 429."""
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
                    max_tokens=2048
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str
                if not is_rate_limit:
                    logger.warning(f"Groq text call failed: {e}. Attempting OpenRouter fallback.")
                else:
                    logger.warning(f"Groq rate limit hit (429): {e}. Falling back to OpenRouter ({OPENROUTER_TEXT_FALLBACK}).")

        # Fallback to OpenRouter Free Text
        if not self._openrouter_client:
            raise ValueError("OpenRouter client not initialized. Cannot perform text fallback.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resp = self._openrouter_client.chat.completions.create(
            model=OPENROUTER_TEXT_FALLBACK,
            messages=messages,
            temperature=0.1,
            max_tokens=2048
        )
        return resp.choices[0].message.content or ""


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
