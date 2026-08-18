import os
import json
import re
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from pydantic import ValidationError

from backend.models import ReceiptData, ReceiptItem, DiscountDetail, TaxBreakdown
from backend.llm_provider import get_vision_client

# Load environment variables (.env)
load_dotenv()

PRIMARY_EXTRACTION_PROMPT = """You are an expert receipt OCR and extraction assistant.
Analyze the provided receipt image carefully and extract all information into a single JSON object.

The JSON MUST strictly conform to this structure:
{
  "restaurant_name": "string or null",
  "bill_number": "string or null",
  "items": [
    {
      "name": "string",
      "qty": 1.0,
      "unit_price": 0.0,
      "amount": 0.0
    }
  ],
  "subtotal": 0.0,
  "discount": {
    "amount": 0.0,
    "label": "string or null"
  },
  "service_charge": 0.0,
  "tax": {
    "cgst": 0.0,
    "sgst": 0.0,
    "total_tax": 0.0
  },
  "round_off": 0.0,
  "grand_total": 0.0
}

Rules:
1. Return ONLY valid JSON wrapped in ```json ... ``` or directly as raw JSON.
2. Extract all individual line items accurately with item name, quantity (qty), unit price (unit_price), and line amount (amount).
3. If an item quantity is not explicitly shown, default qty to 1.0.
4. Extract tax breakdowns (CGST, SGST, Total Tax) if present. If total tax is shown without CGST/SGST, set total_tax.
5. If a discount is present, extract it as an object with "amount" (positive float) and "label" (e.g. "Happy Hour 10%"). If no discount, set discount to null.
6. Extract service charge / tip if present (positive float); otherwise set to null.
7. Extract round_off adjustment if present (+/- float); otherwise set to null.
8. grand_total must be the final payable bill total (positive float).
9. Do not fabricate values; read directly from the receipt image.
"""

STRICT_FALLBACK_PROMPT = """CRITICAL INSTRUCTION: Your previous response failed validation or JSON parsing.
You MUST return ONLY a strictly valid, parseable JSON object representing the receipt in the image, without commentary or markdown other than ```json codeblock.

Required JSON Structure:
{
  "restaurant_name": "string or null",
  "bill_number": "string or null",
  "items": [
    {
      "name": "string",
      "qty": 1.0,
      "unit_price": 0.0,
      "amount": 0.0
    }
  ],
  "subtotal": 0.0,
  "discount": {
    "amount": 0.0,
    "label": "string or null"
  },
  "service_charge": 0.0,
  "tax": {
    "cgst": 0.0,
    "sgst": 0.0,
    "total_tax": 0.0
  },
  "round_off": 0.0,
  "grand_total": 0.0
}

Ensure:
1. "items" is a list of item objects with "name", "qty", "unit_price", "amount".
2. "grand_total" is a valid numeric float.
3. If discount, service_charge, tax, or round_off are not present, set them to null.
4. All numeric values must be numbers (e.g. 150.0), not strings.
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


def _run_self_checks(receipt: ReceiptData) -> List[str]:
    """Recomputes subtotal and grand total, checking against printed receipt values.
    
    Self-check algorithm:
    1. Per-item math check: verify abs(qty * unit_price - amount) < 0.5.
    2. Recompute subtotal from summed item amounts.
    3. Recompute expected grand total: (subtotal - discount + service_charge + tax + round_off).
    4. Compare both against printed subtotal / grand_total and flag discrepancies (> 0.05).
    """
    flags: List[str] = []

    # 1. Per-item math check: verify abs(qty * unit_price - amount) < 0.5
    for item in receipt.items:
        computed_item_amt = round(item.qty * item.unit_price, 2)
        diff = abs(computed_item_amt - round(item.amount, 2))
        if diff >= 0.5:
            flags.append(
                f"Line item math mismatch for '{item.name}': {item.qty} × {item.unit_price:.2f} = {computed_item_amt:.2f} != printed amount {item.amount:.2f}"
            )

    # 2. Recompute subtotal from summed item amounts
    computed_subtotal = round(sum(item.amount for item in receipt.items), 2)
    if receipt.subtotal is not None:
        if abs(receipt.subtotal - computed_subtotal) > 0.05:
            flags.append(
                f"Subtotal mismatch: item sum ({computed_subtotal:.2f}) != printed subtotal ({receipt.subtotal:.2f})"
            )

    # 3. Determine base subtotal for grand total verification
    base_subtotal = receipt.subtotal if receipt.subtotal is not None else computed_subtotal

    # 4. Resolve discount amount
    discount_amount = receipt.discount.amount if receipt.discount else 0.0

    # 5. Resolve service charge
    service_charge = receipt.service_charge or 0.0

    # 6. Resolve tax amount
    tax_amount = 0.0
    if receipt.tax:
        if receipt.tax.total_tax is not None:
            tax_amount = receipt.tax.total_tax
        else:
            cgst = receipt.tax.cgst or 0.0
            sgst = receipt.tax.sgst or 0.0
            tax_amount = cgst + sgst

    # 7. Resolve round off
    round_off = receipt.round_off or 0.0

    # 8. Recompute expected grand total
    expected_grand_total_raw = base_subtotal - discount_amount + service_charge + tax_amount
    expected_grand_total_with_round = round(expected_grand_total_raw + round_off, 2)
    expected_grand_total_rounded_int = round(expected_grand_total_raw)

    printed_gt = round(receipt.grand_total, 2)

    # Allow match if it matches with explicit round_off or standard mathematical rounding
    is_match = (
        abs(expected_grand_total_with_round - printed_gt) <= 0.05
        or abs(round(expected_grand_total_raw, 2) - printed_gt) <= 0.05
        or abs(expected_grand_total_rounded_int - printed_gt) <= 0.05
    )

    if not is_match:
        flags.append(
            f"Grand total mismatch: computed expected ({expected_grand_total_with_round:.2f}) "
            f"!= printed grand total ({printed_gt:.2f})"
        )

    return flags


def extract_receipt(
    image_bytes: bytes,
    force_fallback: bool = False
) -> ReceiptData:
    """Extracts structured receipt data from image bytes using LLMProvider (Gemini Flash -> OpenRouter fallback).
    
    Args:
        image_bytes: Raw bytes of the receipt image (JPEG, PNG, WEBP, etc.)
        force_fallback: If True, bypasses primary model and uses fallback model directly.
        
    Returns:
        ReceiptData: Pydantic validated receipt object with extraction_flags attached.
        
    Raises:
        ValueError: If extraction fails after retry or JSON/schema validation fails.
    """
    client = get_vision_client()

    # Attempt 1: Primary prompt
    raw_response = ""
    parse_error = None
    used_fb = False
    fb_reason = None
    try:
        raw_response, used_fb, fb_reason = client.generate_vision_with_status(
            prompt=PRIMARY_EXTRACTION_PROMPT,
            image_bytes=image_bytes,
            force_fallback=force_fallback
        )
        parsed_dict = _clean_and_parse_json(raw_response)
        receipt = ReceiptData.model_validate(parsed_dict)
    except (json.JSONDecodeError, ValidationError, Exception) as e:
        parse_error = e

    # Attempt 2: Retry with stricter prompt if attempt 1 failed
    if parse_error is not None:
        if isinstance(parse_error, TimeoutError):
            raise parse_error
        try:
            raw_response, used_fb, fb_reason = client.generate_vision_with_status(
                prompt=STRICT_FALLBACK_PROMPT,
                image_bytes=image_bytes,
                force_fallback=force_fallback
            )
            parsed_dict = _clean_and_parse_json(raw_response)
            receipt = ReceiptData.model_validate(parsed_dict)
        except TimeoutError as retry_timeout:
            raise retry_timeout
        except Exception as retry_err:
            raise ValueError(
                f"Receipt extraction failed after retry. "
                f"Initial error: {parse_error}. Retry error: {retry_err}. "
                f"Raw response: {raw_response}"
            ) from retry_err

    receipt.used_fallback = used_fb
    receipt.fallback_reason = fb_reason

    # Run self-check validations
    flags = _run_self_checks(receipt)
    receipt.extraction_flags = flags

    return receipt

