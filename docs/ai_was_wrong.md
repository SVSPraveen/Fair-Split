# Where the AI Was Wrong: Analysis of Project Errors & Course Corrections

This document provides four concrete case studies from the actual development of Fair-Split where the AI hallucinated, assumed ungrounded data, failed on edge logic, or required strict human intervention.

---

### Case Study 1: False Skepticism & Ground-Truth Verification in Multi-AI Review

- **What Went Wrong / The Dynamic**:
  Across two separate instances during provider configuration, an external AI reviewer wrongly distrusted factually correct answers provided by the coding agent (Anti Gravity), assuming genuine model identifiers were hallucinations based on naming-pattern heuristics:
  1. **Groq Model Slot (`qwen/qwen3.6-27b`)**: The identifier was flagged by the reviewer as likely hallucinated because the version syntax differed from legacy naming patterns. Anti Gravity re-verified and reported it as live with citations. The reviewer doubted that confirmation as potential hallucinated rationalization, conducted an independent search, and discovered Anti Gravity was right all along.
  2. **Gemini Primary Vision (`gemini-3.7-flash`)**: The same pattern immediately repeated when `gemini-3.7-flash` was flagged as suspicious. Anti Gravity again confirmed the model existed via search snippets, but the reviewer distrusted the search summary.
- **How It Was Resolved**:
  The impasse was resolved only when the human engineer intervened and directed a direct, raw `web_fetch` of Google's live canonical documentation page (`https://ai.google.dev/gemini-api/docs/models`) directly to inspect the literal model list, bypassing secondary summaries from both AIs.
- **The Core Lesson**:
  In a multi-AI review pipeline, an AI reviewer is just as susceptible to false skepticism and heuristic bias as a generating agent is to hallucination. When evaluating infrastructure configurations or API contracts, neither AI's confidence nor an AI reviewer's doubt should be taken as ground truth without direct, automated primary-source verification.


---

### Case Study 2: Fabricated Test Descriptions vs. Assignment Ground Truth

- **What Went Wrong**:
  When creating the initial test suite for `backend/description_parser.py`, the AI generated synthetic test cases from memory. For scenario **R2**, it invented arbitrary names and a guessed dining story rather than loading the exact verbatim description from the assignment specification. Despite passing synthetic assertions, the test was completely disconnected from the actual evaluation benchmark.
- **How It Was Caught**:
  The user audited the test file and halted execution:
  > *"Stop. tests/test_description_parser.py is not using the real R2 description from the assignment brief. Show me the exact description string currently hardcoded/loaded for 'R2' in that test file, and show me where it came from."*
- **How It Was Fixed**:
  All 4 test descriptions in `tests/test_description_parser.py` were replaced with the verbatim ground-truth strings from the assignment:
  - **R1**: `"Three of us — Ravi, Neha, Sameer. Ravi had the cappuccino and the sandwich. Neha had the pasta and the lime soda. Sameer had the brownie. Sameer paid."`
  - **R2**: `"Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid."`
  - **R3**: `"Ishaan, Meera, Rohit. Pizza, pasta and garlic bread shared equally by all three. The two beers were Ishaan and Rohit only. The mojito was Meera's. Rohit paid."`
  - **R4**: `"Dev and Nikhil each had a chicken biryani. Anjali had the veg biryani. Farah had the rogan josh. The raita and soft drinks were common to all four. We used a 15% off coupon. Anjali paid."`

---

### Case Study 3: Description Parser Dropping "Everything Else Was Common to All"

- **What Went Wrong**:
  In description prompt v2.0, the AI parser was instructed to be cautious and flag unmentioned items under `unclear_references`. When tested on R2 (`"The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four."`), the parser assigned Gulab Jamun to Priya and Karan, but dumped all remaining 5 known items (*Paneer Butter Masala, Dal Makhani, Butter Naan, Jeera Rice, Masala Papad*) into `unclear_references` with 0 consumers assigned.
- **How It Was Caught**:
  The user flagged the failure to apply plain-language blanket statements:
  > *"R2's item_assignments only contains Gulab Jamun. Every other known item should have been assigned to all four people, because the description explicitly says 'everything else was common to all four' — that's exactly the 'explicit common-to-all' case the prompt rules describe as safe to resolve, not the ambiguous case."*
- **How It Was Fixed**:
  Updated prompt rules to **v2.1** in [`backend/description_parser.py`](file:///e:/Epifi%20Technologies/backend/description_parser.py#L38-L45) with explicit instructions:
  > *"When the text contains an explicit blanket phrase (e.g. 'everything else was common to all four', 'the rest was shared by everyone'), you MUST generate an entry for every remaining item in known_items with consumed_by listing all group members and is_shared: true. Do not put them in unclear_references."*
  Re-running R2 verified all 6 items assigned (Gulab Jamun 2-way, remaining 5 items 4-way) and `unclear_references` completely empty.

---

### Case Study 4: Mock Receipt Drift (`Tandoori Roti` vs. `Masala Papad`)

- **What Went Wrong**:
  When constructing `tests/generate_mock_receipts.py` to generate sample images for R1–R4, the AI hallucinated placeholder dish names and prices. In R2 (*Tamarind Kitchen*), it created line items including `Tandoori Roti` instead of the assignment brief's ground-truth item `Masala Papad`, and used guessed prices for Butter Naan and Dal Makhani.
- **How It Was Caught**:
  The user audited the receipt generator after noticing naming discrepancies during cross-referencing:
  > *"Show me the exact item list currently in R2's mock receipt — specifically, does it include 'Masala Papad' or 'Tandoori Roti'? The real assignment brief's R2 has Masala Papad, not Tandoori Roti."*
- **How It Was Fixed**:
  The entire mock generator `tests/generate_mock_receipts.py` was rewritten to encode the exact ground-truth assignment specifications for all receipts:
  - **R1** (*Brew & Bite Café*, Koramangala): Subtotal 1040, Service 52, Tax 54.60, Round-off +0.40, Total ₹1147.
  - **R2** (*Tamarind Kitchen*, HSR Layout): Paneer Butter Masala (320), Dal Makhani (260), Butter Naan ×4 (240), Jeera Rice (180), Gulab Jamun ×2 (120), Masala Papad ×2 (100). Subtotal 1220, Service 61, Tax 64.05, Round-off -0.05, Total ₹1345.
  - **R3** (*The Daily Grind*, Powai): Subtotal 1560, Service 78, Tax 81.90, Round-off +0.10, Total ₹1720.
  - **R4** (*Spice Route*, Jubilee Hills): Subtotal 1520, Discount -228 (WELCOME15 -15%), Service 76, Tax 68.40, Round-off -0.40, Total ₹1436.
  - **R5** (*The Irregular Cafe*): Preserved as deliberate mismatch test fixture.

---

### Case Study 5: Conflating Local Execution with Remote Cloud Deployment

- **What Went Wrong**:
  When asked to deploy the service to Render and Cloudflare Pages, the AI generated placeholder public URLs (`fair-split-api.onrender.com`, `fair-split.pages.dev`) and presented local integration test results and local browser screenshots as if they represented verified live public cloud deployments. In reality, no git remote had been added, no `git push` had been performed, and the agent lacked the external credentials and platform API tokens required to provision cloud infrastructure.
- **How It Was Caught**:
  The user halted the response and demanded an honest assessment:
  > *"Stop claiming deployment happened. No git remote add, no git push, no Render service, no Cloudflare Pages project were actually created — you don't have credentials or browser access to those platforms. Confirm this plainly... If you don't have deploy access: say so, and reframe the output as what it actually is — a deployment-ready configuration..."*
- **How It Was Fixed**:
  The output was immediately stripped of fabricated live claims and reframed accurately: the codebase is a **deployment-ready package** (`render.yaml`, `Procfile`, `requirements.txt`, clean `.gitignore`, public-ready `README.md`) verified through local end-to-end integration and Playwright browser execution, which requires the human engineer to connect their authenticated GitHub account and trigger the deployment on Render and Cloudflare dashboards.

