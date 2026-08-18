import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ARTIFACT_DIR = Path(r"C:\Users\svspr\.gemini\antigravity-ide\brain\a6bc5697-ec2c-4e24-b1e3-5400bfb76357")
SCREENSHOT_PATH = ARTIFACT_DIR / "r2_browser_result.png"
R2_IMAGE_PATH = Path(r"E:\Epifi Technologies\tests\sample_receipts\R2.png")


def run_browser_test():
    print("Launching real Playwright Chromium browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        print("1. Navigating to http://localhost:3000...")
        page.on("console", lambda msg: print(f"[BROWSER CONSOLE] {msg.text}"))
        page.on("pageerror", lambda err: print(f"[BROWSER ERROR] {err}"))
        page.goto("http://localhost:3000", wait_until="networkidle")

        print("2. Setting receipt file on #receipt-file input...")
        assert R2_IMAGE_PATH.exists(), f"Image not found at {R2_IMAGE_PATH}"
        page.set_input_files("#receipt-file", str(R2_IMAGE_PATH))

        print("2b. Waiting for file preview to load...")
        page.wait_for_selector("#preview-area:not(.hidden)", timeout=10000)

        print("3. Filling natural language description...")
        description_text = (
            "Four of us: Aman, Priya, Karan, Sara. "
            "The Gulab Jamun was shared just by Priya and Karan. "
            "Everything else was common to all four. Priya paid."
        )
        page.fill("#description-input", description_text)

        print("4. Clicking 'Calculate Fair Split' button (#submit-btn)...")
        page.click("#submit-btn")

        print("5. Waiting for results container (#results-container) to render...")
        try:
            page.wait_for_selector("#results-container:not(.hidden)", timeout=60000)
        except Exception as e:
            print("Timeout waiting for #results-container. Checking if #error-card is visible...")
            if page.is_visible("#error-card"):
                print("Error Card Text:", page.inner_text("#error-message"))
            page.screenshot(path=str(ARTIFACT_DIR / "debug_browser_timeout.png"), full_page=True)
            raise e


        # Allow smooth animation/DOM settlement
        page.wait_for_timeout(1000)

        print(f"6. Capturing full-page screenshot to {SCREENSHOT_PATH}...")
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)

        print("7. Extracting rendered results from live DOM...")
        recon_title = page.inner_text("#recon-title")
        grand_total_text = page.inner_text("#stat-grand-total")
        person_sum_text = page.inner_text("#stat-person-sum")
        paid_by_text = page.inner_text("#paid-by-name")

        table_rows = page.query_selector_all("#split-table-body tr")
        row_data = []
        for tr in table_rows:
            cells = [td.inner_text().strip().replace("\n", " ") for td in tr.query_selector_all("td")]
            row_data.append(cells)

        settle_items = [li.inner_text().strip().replace("\n", " ") for li in page.query_selector_all("#settle-up-list li")]
        assumptions = [li.inner_text().strip() for li in page.query_selector_all("#assumptions-list li")]

        browser.close()

        print("\n================ LIVE BROWSER TEST RESULTS ================")
        print(f"Reconciliation Title: {recon_title}")
        print(f"Grand Total: {grand_total_text} | Sum of Person Totals: {person_sum_text}")
        print(f"Payer: {paid_by_text}")
        print("\nTable Rows (from Live DOM):")
        for r in row_data:
            print("  " + " | ".join(r))
        print("\nSettle-Up Transfers (from Live DOM):")
        for s in settle_items:
            print(f"  • {s}")
        print("\nAssumptions (from Live DOM):")
        for a in assumptions:
            print(f"  • {a}")
        print(f"\nScreenshot successfully saved to: {SCREENSHOT_PATH}")
        print("===========================================================")


if __name__ == "__main__":
    run_browser_test()
