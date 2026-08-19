import sys
import json
import base64
import urllib.request
from pathlib import Path

# Ensure root workspace directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure utf-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def test_frontend_complete():
    print("=" * 80)
    print(" FRONTEND & BACKEND INTEGRATED AUDIT VERIFICATION")
    print("=" * 80)

    # 1. Test Static Frontend Server (Port 8000)
    print("\n[1] Checking Frontend Static Server (http://localhost:8000)...")
    try:
        req = urllib.request.urlopen("http://localhost:8000/")
        html = req.read().decode("utf-8")
        assert req.status == 200
        print("--> index.html successfully served (200 OK)")

        # Verify key UI components in HTML
        required_elements = [
            'id="split-form"',
            'id="receipt-file"',
            'id="description-input"',
            'id="submit-btn"',
            'id="settings-toggle-btn"',
            'id="api-config-panel"',
            'data-sample="R1"',
            'data-sample="R2"',
            'data-sample="R3"',
            'data-sample="R4"',
            'id="confidence-banner"',
            'id="reconciliation-banner"',
            'id="split-table"',
            'id="settle-up-list"',
            'id="copy-table-btn"',
            'id="copy-settle-btn"'
        ]
        for elem in required_elements:
            assert elem in html, f"Missing element {elem} in index.html!"
        print("--> All required UI elements and IDs verified in HTML.")
    except Exception as e:
        print(f"FAILED to fetch frontend: {e}")
        raise

    # 2. Test app.js static serve
    print("\n[2] Checking app.js static serve...")
    try:
        req_js = urllib.request.urlopen("http://localhost:8000/app.js")
        js_content = req_js.read().decode("utf-8")
        assert req_js.status == 200
        assert "SAMPLE_PRESETS" in js_content
        assert "renderResults" in js_content
        assert "copyTableBtn" in js_content
        print("--> app.js successfully served with updated preset chips and copy handlers.")
    except Exception as e:
        print(f"FAILED to fetch app.js: {e}")
        raise

    # 3. Test style.css static serve
    print("\n[3] Checking style.css static serve...")
    try:
        req_css = urllib.request.urlopen("http://localhost:8000/style.css")
        css_content = req_css.read().decode("utf-8")
        assert req_css.status == 200
        assert ".confidence-banner" in css_content
        assert ".sample-chip" in css_content
        assert ".fair-toast" in css_content
        print("--> style.css successfully served with all upgraded UI design tokens.")
    except Exception as e:
        print(f"FAILED to fetch style.css: {e}")
        raise

    # 4. Test Backend /health (Port 8000)
    print("\n[4] Checking Backend /health endpoint (http://localhost:8000)...")
    try:
        req_health = urllib.request.urlopen("http://localhost:8000/health")
        health_data = json.loads(req_health.read().decode("utf-8"))
        assert req_health.status == 200
        assert health_data.get("status") == "ok"
        print("--> Backend /health responded with status 'ok' (200 OK).")
    except Exception as e:
        print(f"FAILED to connect to backend: {e}")
        raise

    # 5. Full End-to-End Split Calculation Simulation
    print("\n[5] Simulating Full End-to-End Split Calculation (R2 Sample)...")
    from backend.models import ReceiptData, DescriptionData
    from backend.compute import compute_split

    r2_receipt = ReceiptData(
        restaurant_name="Tamarind Kitchen",
        bill_number="2207",
        items=[
            {"name": "Paneer Butter Masala", "qty": 1.0, "unit_price": 320.0, "amount": 320.0},
            {"name": "Dal Makhani", "qty": 1.0, "unit_price": 260.0, "amount": 260.0},
            {"name": "Butter Naan", "qty": 4.0, "unit_price": 60.0, "amount": 240.0},
            {"name": "Jeera Rice", "qty": 1.0, "unit_price": 180.0, "amount": 180.0},
            {"name": "Gulab Jamun", "qty": 2.0, "unit_price": 60.0, "amount": 120.0},
            {"name": "Masala Papad", "qty": 2.0, "unit_price": 50.0, "amount": 100.0}
        ],
        subtotal=1220.0,
        service_charge=61.0,
        tax={"total_tax": 64.05},
        round_off=-0.05,
        grand_total=1345.0
    )

    r2_desc = DescriptionData(
        people=["Aman", "Priya", "Karan", "Sara"],
        payer="Priya",
        item_assignments=[
            {"item_name": "Paneer Butter Masala", "consumed_by": ["Aman", "Priya", "Karan", "Sara"], "is_shared": True},
            {"item_name": "Dal Makhani", "consumed_by": ["Aman", "Priya", "Karan", "Sara"], "is_shared": True},
            {"item_name": "Butter Naan", "consumed_by": ["Aman", "Priya", "Karan", "Sara"], "is_shared": True},
            {"item_name": "Jeera Rice", "consumed_by": ["Aman", "Priya", "Karan", "Sara"], "is_shared": True},
            {"item_name": "Gulab Jamun", "consumed_by": ["Priya", "Karan"], "is_shared": True},
            {"item_name": "Masala Papad", "consumed_by": ["Aman", "Priya", "Karan", "Sara"], "is_shared": True}
        ]
    )

    split_res = compute_split(r2_receipt, r2_desc)
    print("--> Split computed successfully:")
    print(f"    Grand Total: ₹{split_res.grand_total}")
    print(f"    Sum of Person Totals: ₹{split_res.reconciliation.sum_of_person_totals}")
    print(f"    Confidence: {split_res.confidence.level.upper()}")
    print(f"    Settle-Up Transfers: {len(split_res.settle_up)} transactions")

    assert split_res.reconciliation.matches_bill is True
    assert split_res.confidence.level == "high"
    assert len(split_res.per_person) == 4
    assert len(split_res.settle_up) == 3

    print("\n" + "=" * 80)
    print(" ALL FRONTEND, BACKEND, AND MATH VERIFICATIONS COMPLETED SUCCESSFULLY (5/5)")
    print("=" * 80)


if __name__ == "__main__":
    test_frontend_complete()
