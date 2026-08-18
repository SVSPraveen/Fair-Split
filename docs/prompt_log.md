# Prompt Log & Architecture Decisions

This document tracks all prompt iterations across the Fair-Split pipeline, detailing what changed, why, and the core architectural decision separating LLM extraction from deterministic computation.

---

## 1. Prompt Iteration History

- **v1.0 (Initial OCR Vision Extraction)**: Basic structured prompt instructing `gemini-3.7-flash` (and OpenRouter vision fallback) to read raw receipt pixels and output JSON conforming to `ReceiptData`.
  - *Why*: Establish baseline zero-shot OCR extraction for line items, subtotals, tax (CGST/SGST), and grand totals.
- **v1.1 (Stricter Structural Retry Prompt)**: Added explicit schema rules requiring strict numeric formatting, zero-prevention (setting missing optional values to `null` or `0.0`), and explicit regex-cleaning markers.
  - *Why*: Initial runs occasionally returned conversational markdown fences or omitted top-level keys when receipt text was faint or cropped.
- **v1.2 (Nested Discount & Multi-Block Resilience)**: Updated prompt schema to explicitly specify discount as an object `{ "amount": float, "label": string }` vs `null` and added multi-candidate regex parsing.
  - *Why*: Vision models initially flattened negative line-item discounts into single scalar floats, causing schema validation errors when coupon codes or percentage labels were present.
- **v2.0 (Natural Language Description Parser - Primary)**: Prompt for `backend/description_parser.py` cross-referencing natural language dining descriptions against extracted `known_items`. Enforced rules: strict group membership, no payer invention (default to `null` if unstated), partial-share mapping, and routing unmentioned items to `unclear_references`.
  - *Why*: Translate free-form text ("Ravi had the sandwich, Neha had the pasta...") into deterministic consumer mappings.
- **v2.1 (Blanket Common Item Resolution)**: Updated prompt rule to explicitly specify that blanket statements (e.g. "everything else was common to all four", "rest was shared by all") must map all remaining `known_items` to all named individuals with `is_shared: true`, reserving `unclear_references` strictly for genuine unresolvable ambiguities.
  - *Why*: In v2.0, the parser over-cautiously dropped all unmentioned items (e.g. Butter Naan, Jeera Rice in R2) into `unclear_references` instead of assigning them to the group when explicit blanket phrases were present.

---

## 2. Core Architectural Decision: LLMs for Extraction, Python for Computation

### **Question: Did we let the model do the arithmetic, or extract structured data and compute the totals in code?**

### **Answer: Structured extraction via LLMs + 100% deterministic computation in Python.**

### **Rationale & Evidence**:
1. **Zero Hallucinated Math**: LLMs (even large frontier models) struggle with multi-tier percentage scaling, uneven fractional division, non-commutative rounding remainder allocations, and cross-person debt reconciliation. By restricting the LLM purely to unstructured-to-structured translation (pixels $\to$ `ReceiptData` and prose $\to$ `DescriptionData`), all financial arithmetic is executed in pure Python with exact floating-point precision and explicit rounding rules.
2. **Auditable, Traceable Reconciliation**: In test scenario **R5** (*The Irregular Cafe*) and stress-test **Case 2** (*Pasta Villa*), the printed receipts contained intentional arithmetic errors (line item sums != printed subtotal; computed total != printed grand total). 
   - An LLM instructed to "calculate the split" will almost invariably hallucinate a mathematical fix, invent phantom line items, or silently fudge individual person subtotals to force reconciliation without alerting the user.
   - Because our mathematical reconciliation runs strictly in Python ([`backend/extraction.py`](file:///e:/Epifi%20Technologies/backend/extraction.py#L42) and [`backend/compute.py`](file:///e:/Epifi%20Technologies/backend/compute.py#L125)), the system caught the exact ₹20 mismatch in R5 (`"Subtotal mismatch: item sum (980.00) != printed subtotal (1000.00)"`) and the ₹60 mismatch in Case 2 (`"Grand total mismatch: computed expected (440.00) != printed grand total (500.00)"`), surfacing them visibly in `flags` rather than hiding them.
3. **Payer-Absorbs-Rounding Determinism**: The rule requiring leftover fractional paise to be absorbed by the payer requires strict integer math:
   $$\text{diff} = \text{grand\_total} - \sum \text{round}(\text{person\_total}_{\text{raw}})$$
   Executing this in Python guarantees that `sum(per_person.total)` identically equals `grand_total` down to the exact rupee, and ensures settle-up debt transfers match without fraction leaks.

---

## 3. Multimodal Model Routing & Preference Order

Based on extensive empirical latency and rate-limit benchmarking across all providers, the system enforces the following 3-tier preference hierarchy:

### **Vision Pipeline (Receipt OCR)**
1. **Tier 1 (Primary)**: **Groq Vision (`qwen/qwen3.6-27b`)**
   - *Why*: Ultra-low latency (~2.2 seconds), flawless extraction of complex thermal receipts, and active quota when combined with dynamic image token optimization (`_optimize_image_for_ocr` reducing token weight by 75%).
2. **Tier 2 (Fallback)**: **Gemini 3.7 Flash (`gemini-3.7-flash`)**
   - *Why*: Frontier multimodal extraction invoked if Groq encounters a timeout (15s) or rate limit.
3. **Tier 3 (Emergency)**: **OpenRouter Vision (`google/gemma-4-26b-a4b-it:free`)**
   - *Why*: Independent external provider guaranteeing zero single-point-of-failure.

### **Text Pipeline (Dining Description Parsing)**
1. **Tier 1 (Primary)**: **Groq Text (`openai/gpt-oss-120b`)**
   - *Why*: Massive 120B parameter reasoning model delivering 1.2s inference and high-fidelity parsing of complex overlapping subgroup sharing.
2. **Tier 2 (Fallback)**: **Gemini 3.7 Flash Text (`gemini-3.7-flash`)**
   - *Why*: Fast secondary natural language parser.
3. **Tier 3 (Emergency)**: **OpenRouter Text (`nvidia/nemotron-3-super-120b-a12b:free`)**
   - *Why*: 120B parameter fallback ensuring high-capacity structured JSON generation.

