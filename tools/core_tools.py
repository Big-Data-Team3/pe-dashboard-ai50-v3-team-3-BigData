import json
import re
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from google.cloud import storage
from google.cloud.storage.blob import Blob

print("[DEBUG] core_tools loaded from:", __file__)

# ============================================================
# Add Lab 8 directories to PYTHONPATH FIRST
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAB8_SRC = PROJECT_ROOT / "lab8_structured_pipeline_service" / "src"

sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(LAB8_SRC))


# ============================================================
# Import Lab 8 API (AFTER path setup)
# ============================================================

try:
    from lab8_structured_pipeline_api import (
        load_structured_from_gcs,
        build_payload,
        validate_payload,
        save_payload_to_gcs,
    )
    import lab8_structured_pipeline_api as lab8
    print("[IMPORT] Successfully loaded Lab 8 structured pipeline.")
except Exception as e:
    raise RuntimeError(
        f"[IMPORT ERROR] Could not import lab8_structured_pipeline_api\n"
        f"PROJECT_ROOT={PROJECT_ROOT}\n"
        f"LAB8_SRC={LAB8_SRC}\nReason: {e}"
    )


# ============================================================
# CONFIG
# ============================================================

BUCKET_NAME = "us-central1-pe-dashboard-or-395f6975-bucket"
RUNS_PREFIX = "data/raw/_runs/"
STRUCTURED_PREFIX = "data/structured/"
PAYLOAD_PREFIX = "data/payloads/"

PIPELINE_API = (
    "https://structured-pipeline-dot-glowing-jetty-477417-h9.ue.r.appspot.com/pipeline/run"
)

storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)


# ============================================================
# SAFE JSON LOADER (handles all encoding variants)
# ============================================================

def load_structured_json_safe(gcs_blob):
    """
    Robust loader:
      ✓ Normal JSON → dict
      ✓ JSON string → dict
      ✓ Double-encoded → dict
      ✗ Else → error
    """
    raw = gcs_blob.download_as_text("utf-8").strip()

    # Case 1: Already dict
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            print("[INFO] Normal JSON loaded.")
            return data
    except Exception:
        pass

    # Case 2: JSON string → inner dict
    try:
        inner = json.loads(raw)
        if isinstance(inner, str):
            print("[WARN] JSON string detected — decoding inner object…")
            inner2 = json.loads(inner)
            if isinstance(inner2, dict):
                print("[INFO] String → dict decode success.")
                return inner2
    except Exception:
        pass

    # Case 3: Double-encoded
    try:
        print("[WARN] Trying double-decoding fallback…")
        data = json.loads(json.loads(raw))
        if isinstance(data, dict):
            print("[INFO] Double-decoded JSON fixed.")
            return data
    except Exception:
        pass

    # Case 4: FATAL
    raise RuntimeError(f"❌ Structured JSON corrupted:\n{raw[:500]}")


# ============================================================
# MONKEY PATCH load_structured_from_gcs
# ============================================================

def patched_load_structured_from_gcs(company_id: str):
    remote = f"{STRUCTURED_PREFIX}{company_id}.json"
    blob = bucket.blob(remote)

    if not blob.exists(storage_client):
        raise FileNotFoundError(f"Structured not found: gs://{BUCKET_NAME}/{remote}")

    return load_structured_json_safe(blob)

lab8.load_structured_from_gcs = patched_load_structured_from_gcs
print("[PATCH] load_structured_from_gcs overridden → SAFE loader active")


# ============================================================
# Read latest manifests (safe for empty directories)
# ============================================================

def get_latest_company_ids_from_runs() -> list[str]:

    blobs = list(bucket.list_blobs(prefix=RUNS_PREFIX))

    # Only real blob objects
    manifest_blobs = [
        b for b in blobs
        if isinstance(b, Blob) and b.name.endswith(".json") and "daily_" in b.name
    ]

    if not manifest_blobs:
        raise FileNotFoundError("No daily manifest found in _runs/")

    def extract_date(name):
        m = re.search(r"daily_(\d{8})\.json", name)
        return datetime.strptime(m.group(1), "%Y%m%d") if m else datetime.min

    latest = max(manifest_blobs, key=lambda b: extract_date(b.name))
    print(f"[INFO] Latest manifest: {latest.name}")

    text = latest.download_as_text("utf-8")
    records = json.loads(text)

    return sorted({
        r["company_id"]
        for r in records
        if r.get("status") == "ok"
    })


# ============================================================
# Trigger Cloud Run
# ============================================================

def trigger_structured_extraction(company_id: str):
    print(f"[INFO] Cloud Run: extracting '{company_id}'…")

    resp = requests.post(PIPELINE_API, json={"company_name": company_id})
    if resp.status_code != 200:
        raise RuntimeError(f"Cloud Run error: {resp.text}")

    print("[INFO] Cloud Run accepted request.")
    return resp.json()


# ============================================================
# MAIN PAYLOAD CREATOR
# ============================================================

async def create_payload_for_company(company_id: str) -> dict:

    gcs_blob = bucket.blob(f"{STRUCTURED_PREFIX}{company_id}.json")

    # Try reading structured
    try:
        print(f"[INFO] Loading structured for {company_id}…")
        structured = load_structured_json_safe(gcs_blob)
    except Exception:
        print(f"[WARN] No structured found → triggering Cloud Run for {company_id}")
        trigger_structured_extraction(company_id)

        # Wait for output
        for i in range(25):
            gcs_blob = bucket.blob(f"{STRUCTURED_PREFIX}{company_id}.json")
            if gcs_blob.exists(storage_client):
                print("[INFO] Structured appeared — loading…")
                structured = load_structured_json_safe(gcs_blob)
                break
            time.sleep(2)
        else:
            raise RuntimeError("Structured file never appeared!")

    # Build payload
    print("[INFO] Building payload…")
    payload = build_payload(company_id, structured)

    print("[INFO] Validating payload…")
    validate_payload(payload)

    print("[INFO] Saving payload to GCS…")
    uri = save_payload_to_gcs(company_id, payload)

    print(f"[SUCCESS] Payload saved → {uri}")
    return payload


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":

    print("=== Running core_tools tests ===")

    # Manifest check
    try:
        ids = get_latest_company_ids_from_runs()
        print("Latest companies:", ids[:10])
    except Exception as e:
        print("[FAIL] Manifest error:", e)

    # Payload generator
    try:
        import asyncio
        cid = input("\nEnter company_id: ").strip()
        result = asyncio.run(create_payload_for_company(cid))
        print("Payload keys:", result.keys())
    except Exception as e:
        print("[FAIL] Payload error:", e)
