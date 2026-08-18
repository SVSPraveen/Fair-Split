# Fair-Split — Itemized Bill Splitting & Fairness Engine

Fair-Split is a deterministic receipt OCR, natural language consumption parser, and proportional bill settlement engine built with Python, FastAPI, and vanilla web standards.

---

## 🌟 Key Capabilities

1. **Multimodal Receipt OCR Extraction (`backend/extraction.py`)**:
   - Primary vision extraction via `gemini-3.7-flash` (Google AI Studio) with automatic 429 rate-limit fallback to OpenRouter (`google/gemma-4-26b-a4b-it:free`).
   - Extracts restaurant name, bill number, itemized line items (quantities, unit prices, total amounts), discounts, service charges, taxes (CGST/SGST/total), and grand totals.
   - **Mathematical Self-Check Verification**: Automatically computes line-item sums and total additions; flags printed discrepancies in `extraction_flags`.

2. **Group Dining Description Parser (`backend/description_parser.py`)**:
   - Cross-references plain-English consumption descriptions against extracted `known_items`.
   - Maps individual items, arbitrary subset shared items (e.g. 2 of 4, 3 of 5), explicit blanket sharing statements (*"everything else was common to all"*), unmatched item mentions, and identifies the bill payer without hallucinating unstated payers.

3. **Deterministic Settlement Engine (`backend/compute.py`)**:
   - **Zero LLM Calls / Pure Python Arithmetic**: 100% auditable and reproducible.
   - **Proportional Allocations**: Allocates GST, service charges, and bill discounts strictly proportional to each person's pre-tax subtotal.
   - **Payer-Only Remainder Absorption**: Rounds individual shares independently to the nearest rupee; any fractional remainder ($\pm ₹1-2$) is absorbed directly by the payer to ensure `sum(person_totals) == grand_total`.
   - **Debt Settle-Up**: Generates direct-to-payer reimbursement instructions (`from` $\to$ `to`).

4. **Minimal Web Frontend (`/frontend`)**:
   - Zero-build vanilla HTML5, CSS3, and modern JavaScript.
   - Client-side image preprocessing (base64 conversion with data-URI stripping).
   - Dynamic reconciliation badges, itemized split tables, settle-up cards, and quality flag banners.

---

## 📁 Repository Structure

```text
├── backend/
│   ├── __init__.py
│   ├── compute.py              # Pure Python deterministic split computation engine
│   ├── description_parser.py   # Natural language consumption parser (Groq / OpenRouter)
│   ├── extraction.py           # Receipt vision OCR extraction & self-check module
│   ├── llm_provider.py         # Multi-tier provider abstraction & fallback handling
│   ├── main.py                 # FastAPI application with POST /split and GET /health
│   └── models.py               # Pydantic schemas (ReceiptData, SplitResult, etc.)
├── docs/
│   ├── ai_was_wrong.md         # Case studies of AI errors, false skepticism, & fixes
│   ├── edge_cases.md           # Documentation & verdicts for 11 stress-test edge cases
│   └── prompt_log.md           # Prompt version history & architecture rationale
├── frontend/
│   ├── app.js                  # Frontend controller & dynamic DOM rendering
│   ├── index.html              # Clean single-page application UI
│   └── style.css               # Clean, accessible styling
├── prompts/
│   └── log.md                  # Prompt engineering change log
├── tests/
│   ├── sample_receipts/        # Ground-truth receipt images (R1–R5)
│   ├── generate_mock_receipts.py # Ground-truth mock receipt generator
│   ├── test_api.py             # FastAPI TestClient integration suite
│   ├── test_browser_playwright.py # Playwright real-browser UI automation test
│   ├── test_compute.py         # Pure computation unit tests across R1–R4
│   ├── test_description_parser.py # Description parser tests with verbatim strings
│   ├── test_edge_cases.py      # 11-scenario stress-test suite
│   ├── test_extraction.py      # Receipt OCR extraction test suite
│   └── test_frontend_simulation.py # Frontend HTTP and simulation test
├── .env.example
├── .gitignore
├── Procfile                    # Web service definition for Render / Heroku
├── render.yaml                 # Render Blueprint deployment configuration
├── requirements.txt            # Production dependencies
└── README.md
```

---

## 🚀 Local Development Quickstart

### 1. Prerequisites & Installation

```bash
# Clone repository
git clone <your-repo-url>
cd fair-split

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables Configuration

Copy `.env.example` to `.env` and configure your API keys:

```env
# Gemini API Key (Google AI Studio)
GEMINI_API_KEY=your_gemini_api_key_here

# Groq API Key
GROQ_API_KEY=your_groq_api_key_here

# OpenRouter API Key (Fallback)
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### 3. Run Backend API Server

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### 4. Run Frontend

Serve the `frontend/` directory with any static server:

```bash
python -m http.server 3000 --directory frontend
```

Open `http://localhost:3000` in your browser.

---

## 🧪 Test Suites Execution

```bash
# 1. Test OCR Extraction against ground-truth R1-R5 receipts
python tests/test_extraction.py

# 2. Test Description Parser against verbatim assignment strings
python tests/test_description_parser.py

# 3. Test Deterministic Computation Engine
python tests/test_compute.py

# 4. Test FastAPI Application Endpoints
python tests/test_api.py

# 5. Run Comprehensive 11-Scenario Edge-Case Stress Suite
python tests/test_edge_cases.py

# 6. Run Real Playwright Browser End-to-End Test
python tests/test_browser_playwright.py
```

---

## 🌐 Public Deployment & Architecture

- **Backend**: Deployed to Render as a Python Web Service (`uvicorn backend.main:app --host 0.0.0.0 --port $PORT`).
- **Frontend**: Deployed to Cloudflare Pages (static HTML/CSS/JS with `API_BASE_URL` pointing to the public backend endpoint).
- **CORS**: Configured with `allow_origins=["*"]` to allow browser clients from any origin.
