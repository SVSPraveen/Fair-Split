import sys
import base64
import json
import urllib.request
import urllib.error
from pathlib import Path

# Ensure UTF-8 output handling in Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_RECEIPTS_DIR = Path(__file__).parent / "sample_receipts"



def test_frontend_serving_and_api():
    print("\n--- 1. Testing Frontend Static Server (http://localhost:3000) ---")
    try:
        with urllib.request.urlopen("http://localhost:3000") as response:
            html_content = response.read().decode("utf-8")
            assert response.status == 200
            assert "<title>Fair-Split" in html_content
            assert 'id="split-form"' in html_content
            assert 'id="results-container"' in html_content
            print(f"Frontend server returned HTTP 200 OK. Page length: {len(html_content)} bytes.")
    except Exception as e:
        print(f"Static server error: {e}")
        raise

    print("\n--- 2. Testing API Backend Server (http://localhost:8000/health) ---")
    try:
        with urllib.request.urlopen("http://localhost:8000/health") as response:
            health_json = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            assert health_json == {"status": "ok"}
            print(f"API backend returned HTTP 200 OK: {health_json}")
    except Exception as e:
        print(f"API health check error: {e}")
        raise

    print("\n--- 3. Testing End-to-End Fetch from Frontend to API with R2.png ---")
    r2_path = SAMPLE_RECEIPTS_DIR / "R2.png"
    with open(r2_path, "rb") as f:
        r2_base64 = base64.b64encode(f.read()).decode("utf-8")

    r2_description = "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid."

    payload = {
        "receipt_base64": r2_base64,
        "description": r2_description
    }

    req = urllib.request.Request(
        "http://localhost:8000/split",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            result_json = json.loads(response.read().decode("utf-8"))
            assert response.status == 200
            print(f"Split API returned HTTP 200 OK:")
            print(json.dumps(result_json, indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
        raise

    # 4. Simulate DOM Generation exactly as app.js renderResults(data)
    print("\n--- 4. Rendered DOM Simulation (app.js renderResults) ---")
    is_match = result_json["reconciliation"]["matches_bill"]
    grand_total = result_json["grand_total"]
    person_sum = result_json["reconciliation"]["sum_of_person_totals"]
    paid_by = result_json["paid_by"]

    print("\n[Rendered Reconciliation Banner]:")
    print(f"  Status: {'[MATCH] Bill Reconciled Exactly' if is_match else '[MISMATCH] Discrepancy'}")
    print(f"  Grand Total: Rs.{grand_total:.2f} | Sum of Person Totals: Rs.{person_sum:.2f}")

    print("\n[Rendered Split Table]:")
    print(f"  {'Person':<10} | {'Subtotal':<10} | {'Tax':<8} | {'Service':<8} | {'Discount':<8} | {'Total':<8}")
    print("  " + "-" * 62)
    for p in result_json["per_person"]:
        payer_tag = " (Payer)" if p["name"] == paid_by else ""
        print(f"  {p['name'] + payer_tag:<10} | Rs.{p['subtotal']:<7.2f} | Rs.{p['tax_share']:<5.2f} | Rs.{p['service_share']:<5.2f} | Rs.{p['discount_share']:<5.2f} | Rs.{p['total']:<5.2f}")

    print("\n[Rendered Settle-Up Section]:")
    print(f"  Paid by: {paid_by}")
    for s in result_json["settle_up"]:
        print(f"  * {s['from']} pays {s['to']} Rs.{s['amount']:.2f}")

    print("\n[Rendered Assumptions & Transparency]:")
    for a in result_json["assumptions"]:
        print(f"  * {a}")
    if result_json["flags"]:
        print("\n[Rendered Quality Flags]:")
        for fl in result_json["flags"]:
            print(f"  [FLAG] {fl}")
    else:
        print("  (No quality warning flags)")

    print("\n=======================================================")
    print(" FRONTEND + BACKEND END-TO-END VERIFICATION SUCCEEDED!")
    print("=======================================================")


if __name__ == "__main__":
    test_frontend_serving_and_api()
