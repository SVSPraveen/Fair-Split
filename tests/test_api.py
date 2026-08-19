import sys
import base64
import json
from pathlib import Path

# Ensure root workspace directory is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
SAMPLE_RECEIPTS_DIR = Path(__file__).parent / "sample_receipts"


def test_health_endpoint():
    print("\n--- Testing GET /health ---")
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response.json().get("status") == "ok"
    print("Health response:", response.json())
    print("--> GET /health PASSED")


def test_split_endpoint_valid_r2():
    print("\n--- Testing POST /split with Real R2 (Tamarind Kitchen) ---")
    r2_path = SAMPLE_RECEIPTS_DIR / "R2.png"
    assert r2_path.exists(), f"Sample receipt image missing: {r2_path}"

    with open(r2_path, "rb") as f:
        r2_base64 = base64.b64encode(f.read()).decode("utf-8")

    r2_description = "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid."

    payload = {
        "receipt_base64": r2_base64,
        "description": r2_description
    }

    response = client.post("/split", json=payload)
    print(f"Response Status Code: {response.status_code}")
    print("\n[Full Response JSON for R2]:")
    print(json.dumps(response.json(), indent=2))

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    # Validations
    assert data["grand_total"] == 1345.0
    assert data["reconciliation"]["matches_bill"] is True
    assert data["reconciliation"]["sum_of_person_totals"] == 1345.0
    assert data["paid_by"] == "Priya"
    assert len(data["per_person"]) == 4
    assert len(data["settle_up"]) == 3
    print("\n--> POST /split R2 PASSED")


def test_split_endpoint_malformed_base64():
    print("\n--- Testing POST /split with Malformed Base64 ---")
    payload = {
        "receipt_base64": "this_is_not_valid_base64_!@#$%",
        "description": "Four of us went for dinner."
    }

    response = client.post("/split", json=payload)
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {json.dumps(response.json(), indent=2)}")

    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    assert "Invalid base64 encoding" in response.json()["detail"]
    print("--> POST /split Malformed Base64 PASSED (Returned 400 with clean error message)")


if __name__ == "__main__":
    test_health_endpoint()
    test_split_endpoint_valid_r2()
    test_split_endpoint_malformed_base64()
    print("\n=======================================================")
    print(" ALL API TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")
