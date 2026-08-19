import os
import json
import re
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv
from pydantic import ValidationError

from backend.models import DescriptionData, ItemAssignment
from backend.llm_provider import get_text_client

# Load environment variables (.env)
load_dotenv()

PRIMARY_DESCRIPTION_PROMPT_TEMPLATE = """You are an expert bill-splitting and group dining description parser.
Given a dining group description and a list of known receipt item names, parse the text into structured JSON.

Known Receipt Items:
{known_items_json}

Description:
\"\"\"{description}\"\"\"

Required JSON Schema:
{{
  "people": ["string"],
  "payer": "string or null",
  "item_assignments": [
    {{
      "item_name": "string",
      "consumed_by": ["string"],
      "is_shared": true
    }}
  ],
  "unmatched_mentions": ["string"],
  "unclear_references": ["string"],
  "parsing_assumptions": ["string"]
}}

CRITICAL RULES:
1. Return ONLY valid JSON wrapped in ```json ... ``` or directly as raw JSON.
2. "people": List all distinct individuals identified in the group.
3. "payer": Identify who paid. If NOT explicitly stated, set "payer" to null. NEVER invent or guess a payer.
4. "item_assignments":
   - Map every mentioned item to the closest name in Known Receipt Items.
   - PARTIAL SHARING: If a subset of people shared an item (e.g. "Arjun and Meena shared the pizza", "2 of us had the beer"), list ONLY those individuals in consumed_by with is_shared: true. The split amount is divided equally among them automatically.
   - BLANKET STATEMENTS: If description says "everything else was common to all" or similar, assign ALL remaining unassigned known items to ALL people.
   - FUZZY MATCHING: Map abbreviated/informal mentions to the closest Known Receipt Item (e.g. "tikka" to "Chicken Tikka Starter", "naan" to "Garlic Naan"). Note the mapping in parsing_assumptions.
5. "unmatched_mentions": Only add if there is genuinely NO plausible match in Known Receipt Items.
6. "unclear_references": Ambiguous phrases that cannot be confidently assigned. Never silently drop them.
7. "parsing_assumptions": Document every inference (e.g. "tikka mapped to Chicken Tikka Starter", "2 of us interpreted as Arjun and Meena").
"""


STRICT_DESCRIPTION_RETRY_PROMPT_TEMPLATE = """CRITICAL INSTRUCTION: Your previous response failed schema validation or JSON decoding.
You MUST return ONLY a strictly valid, parseable JSON object matching the DescriptionData schema.

Known Receipt Items:
{known_items_json}

Description:
\"\"\"{description}\"\"\"

Required JSON Schema:
{{
  "people": ["string"],
  "payer": null,
  "item_assignments": [
    {{
      "item_name": "string",
      "consumed_by": ["string"],
      "is_shared": true
    }}
  ],
  "unmatched_mentions": [],
  "unclear_references": [],
  "parsing_assumptions": []
}}

Rules:
1. When description says "everything else was common to all", assign every remaining item from Known Receipt Items to all people in item_assignments.
2. Ensure all list fields are arrays of strings/objects, payer is string or null, and output is strictly valid JSON without markdown commentary.
"""


def _clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """Strips reasoning tags and robustly extracts JSON from model response text."""
    # 1. Strip <think>...</think> tags if present
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # 2. Try all markdown json code blocks
    code_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    for block in code_blocks:
        try:
            parsed = json.loads(block.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    # 3. Try finding outermost { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = cleaned[first_brace:last_brace + 1]
        try:
            parsed = json.loads(json_candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # 4. Final attempt on raw cleaned string
    return json.loads(cleaned)


def parse_description(
    description: str,
    known_items: List[str],
    force_fallback: bool = False
) -> DescriptionData:
    """Parses a group dining description against known receipt items using LLMProvider text client.
    
    Args:
        description: Natural language text describing the dining party and consumption.
        known_items: List of line item names extracted from the receipt.
        force_fallback: If True, bypasses primary Groq model and uses OpenRouter text fallback.
        
    Returns:
        DescriptionData: Pydantic validated structured representation of assignments and flags.
        
    Raises:
        ValueError: If parsing fails after retry or schema validation fails.
    """
    client = get_text_client()
    known_items_json = json.dumps(known_items, indent=2)

    prompt = PRIMARY_DESCRIPTION_PROMPT_TEMPLATE.format(
        known_items_json=known_items_json,
        description=description.strip()
    )

    raw_response = ""
    parse_error = None
    used_fb = False
    fb_reason = None

    # Attempt 1: Primary prompt
    try:
        raw_response, used_fb, fb_reason = client.generate_text_with_status(
            prompt=prompt,
            force_fallback=force_fallback
        )
        parsed_dict = _clean_and_parse_json(raw_response)
        desc_obj = DescriptionData.model_validate(parsed_dict)
        desc_obj.used_fallback = used_fb
        desc_obj.fallback_reason = fb_reason
        return desc_obj
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        parse_error = e

    # Attempt 2: Retry with strict prompt
    if isinstance(parse_error, TimeoutError):
        raise parse_error

    retry_prompt = STRICT_DESCRIPTION_RETRY_PROMPT_TEMPLATE.format(
        known_items_json=known_items_json,
        description=description.strip()
    )
    try:
        raw_response, used_fb, fb_reason = client.generate_text_with_status(
            prompt=retry_prompt,
            force_fallback=force_fallback
        )
        parsed_dict = _clean_and_parse_json(raw_response)
        desc_obj = DescriptionData.model_validate(parsed_dict)
        desc_obj.used_fallback = used_fb
        desc_obj.fallback_reason = fb_reason
        return desc_obj
    except TimeoutError as retry_timeout:
        raise retry_timeout
    except Exception as retry_err:
        raise ValueError(
            f"Description parsing failed after retry. "
            f"Initial error: {parse_error}. Retry error: {retry_err}. "
            f"Raw response: {raw_response}"
        ) from retry_err

