# Fair-Split

A receipt parsing, itemized bill splitting, and fairness computation engine built with Python & FastAPI.

## Project Structure

```
fair-split/
├── backend/
│   ├── __init__.py
│   ├── extraction.py      # Receipt OCR extraction module (Groq Vision / Gemini)
│   └── models.py          # Pydantic schema models for receipt representation
├── frontend/              # Frontend UI (placeholder)
├── prompts/
│   └── log.md             # Prompt versioning and engineering log
├── tests/
│   ├── sample_receipts/   # Sample receipt images (R1–R4)
│   ├── generate_mock_receipts.py # Mock receipt image generator
│   └── test_extraction.py # Test suite for receipt extraction module
├── .env.example           # Example environment variables
├── .gitignore
└── README.md
```

## Features

- **Receipt OCR & Structured Extraction**: Extracts line items (name, quantity, unit price, line amount), subtotals, tax breakdown (CGST/SGST/total), discounts, service charges, round-off, and grand total.
- **Mathematical Self-Check Verification**:
  - Automatically recomputes subtotal from individual line item amounts.
  - Recomputes grand total from `(subtotal - discount + service_charge + tax + round_off)`.
  - Flags any discrepancies or arithmetic mismatches in `extraction_flags`.
- **Fault-Tolerant Parsing & Retry**:
  - Automatically retries once with a stricter fallback prompt upon schema validation or JSON parse failure before raising an explicit exception.
- **Vision Model Support**:
  - Primary Vision Model: Groq `qwen/qwen3.6-27b` (configurable via `GROQ_VISION_MODEL`).

## Setup & Quickstart

1. **Install Dependencies**:
   ```bash
   pip install fastapi uvicorn pydantic python-dotenv groq pillow
   ```

2. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_VISION_MODEL=qwen/qwen3.6-27b
   ```

3. **Generate Synthetic Sample Receipts**:
   ```bash
   python tests/generate_mock_receipts.py
   ```

4. **Run Extraction Test Suite**:
   ```bash
   python tests/test_extraction.py
   ```
