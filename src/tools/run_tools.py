# ------------------------------------------------------------
# MCP TOOL: get_companies_from_runs()
# ------------------------------------------------------------
# Tool name: runs.get_companies
# ------------------------------------------------------------

import json
import re
from typing import List
from datetime import datetime

from google.cloud import storage
from google.cloud.storage.blob import Blob


BUCKET_NAME = "us-central1-pe-dashboard-or-395f6975-bucket"
RUNS_PREFIX = "data/raw/_runs/"

storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)


# ------------------------------------------------------------
# Helper: locate newest daily_YYYYMMDD.json
# ------------------------------------------------------------
def _get_latest_runs_blob() -> Blob:
    blobs = list(bucket.list_blobs(prefix=RUNS_PREFIX))

    daily_files = [
        b for b in blobs
        if isinstance(b, Blob) and b.name.endswith(".json") and "daily_" in b.name
    ]

    if not daily_files:
        raise FileNotFoundError("No daily_YYYYMMDD.json run files found in GCS.")

    def extract_date(blob_name: str):
        m = re.search(r"daily_(\d{8})\.json", blob_name)
        return datetime.strptime(m.group(1), "%Y%m%d") if m else datetime.min

    return max(daily_files, key=lambda b: extract_date(b.name))


# ------------------------------------------------------------
# MCP Tool: get_companies()
# ------------------------------------------------------------
def get_companies() -> List[str]:
    """
    Return sorted list of company_ids from the latest daily_YYYYMMDD.json in _runs/
    """
    latest_blob = _get_latest_runs_blob()

    raw_json = latest_blob.download_as_text(encoding="utf-8")   # <-- FIXED
    records = json.loads(raw_json)

    companies = sorted({
        r["company_id"]
        for r in records
        if r.get("status") == "ok" and r.get("company_id")
    })

    return companies


# ------------------------------------------------------------
# Local test mode
# ------------------------------------------------------------
if __name__ == "__main__":
    print("[LOCAL TEST] Companies in latest run file:\n")
    print(get_companies())
