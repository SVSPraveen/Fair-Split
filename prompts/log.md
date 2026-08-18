# Prompt Log & Provider Configuration

## Synthetic Test Data Note
- **2026-08-19 (Test Dataset R1–R4)**: Generated 4 synthetic receipt images (`R1.png`, `R2.png`, `R3.png`, `R4.png`) in `tests/sample_receipts/` using Pillow with standard receipt layouts (covering multi-item dining, discounts, CGST/SGST taxes, service charge, and round-offs) as synthetic stand-ins until real physical receipt photos are provided.
- **2026-08-19 (Mismatch Test Case R5)**: Added `R5.png` ("The Irregular Cafe") with an intentional 20-rupee reconciliation mismatch between summed line items (980.00: Pizza 400 + Bread 180 + Coffee 400) and printed subtotal (1000.00) to test self-check reconciliation and ensure quality warnings are appended to `extraction_flags`.

## Prompt Version History
- **v1.0 (Initial Vision Extraction)**: Initial prompt instructing vision model to perform receipt OCR and structure data into JSON conforming strictly to `ReceiptData` schema (restaurant_name, bill_number, items, subtotal, discount, service_charge, tax with CGST/SGST, round_off, grand_total).
- **v1.1 (Stricter Fallback Prompt for Retry)**: Stricter retry prompt activated when initial response fails JSON parsing or misses required keys. Added explicit structural constraints, zero-prevention for missing optional fields (setting them to null/0.0), and strict schema enforcement.
- **v1.2 (Nested Discount & Multi-Block Resilience)**: Updated prompt schema to explicitly specify discount object `{ "amount": float, "label": string }` vs null to prevent scalar float assignment when discount deductions are present. Added multi-candidate regex parsing and Pydantic before-validators for resilient currency/scalar normalization.
- **v2.0 (Natural Language Description Parser - Primary)**: Prompt for `backend/description_parser.py` cross-referencing natural language dining descriptions with `known_items` from receipt extraction. Enforces strict rules: no payer invention (defaults to null if unstated), partial share mapping, routing unknown items to `unmatched_mentions`, routing ambiguity and non-explicit shared defaults to `unclear_references`, and logging inferences in `parsing_assumptions`.
- **v2.1 (Description Parser Strict Retry)**: Stricter structural retry prompt to enforce valid JSON adhering to `DescriptionData` Pydantic schema on initial parse or validation failure.

## LLM Provider Architecture & Model Slot Configuration (2026-08-19)
A unified multi-tier provider abstraction was established in `backend/llm_provider.py` with automatic 429 rate-limit fallback:

1. **Gemini Primary (Vision)**:
   - **Model ID**: `gemini-3.7-flash` (Alias: `gemini-flash-latest`)
   - **Why**: Native multimodal foundation model with superior OCR resolution, zero-shot structured JSON extraction, and high context window.
   - **Rate Limits (Free Tier)**: 15 RPM, 1,000,000 TPM, ~1,500 RPD.

2. **Groq Primary (Text)**:
   - **Model ID**: `openai/gpt-oss-120b` (or `qwen/qwen3.6-27b`)
   - **Why**: Ultra-fast LPU inference latency (<300ms) optimal for high-throughput text operations and description parsing.
   - **Rate Limits (Free Tier)**: 30 RPM, 30,000 TPM, 14,400 RPD.

3. **OpenRouter Vision Fallback**:
   - **Model ID**: `google/gemma-4-26b-a4b-it:free` (Secondary: `nvidia/nemotron-nano-12b-v2-vl:free`)
   - **Why**: Verified active multimodal model available on OpenRouter free tier supporting text+image inputs on 429 rate limit triggers.
   - **Rate Limits (Free Tier)**: 20 RPM, 200 RPD.

4. **OpenRouter Text Fallback**:
   - **Model ID**: `nvidia/nemotron-3-super-120b-a12b:free` (Secondary: `openai/gpt-oss-20b:free`)
   - **Why**: Verified high-performance open-weight text instruction model on OpenRouter free tier for text-only fallback.
   - **Rate Limits (Free Tier)**: 20 RPM, 200 RPD.

## Computation & Arithmetic Design Decisions
- **2026-08-19 (Payer-Absorbs-Rounding Tradeoff)**: The compute engine rounds each individual's total independently to the nearest rupee and assigns the net leftover rounding discrepancy (`diff = grand_total - sum_of_rounded_totals`, typically ±₹1–2) directly into the payer's displayed total. Tradeoff: The payer's total can be ₹1–2 higher than an identical non-payer's total purely due to this rounding remainder absorption, ensuring that `sum(per_person.total)` exactly equals `grand_total` and debt settle-up transfers balance without floating-point fraction leaks.

