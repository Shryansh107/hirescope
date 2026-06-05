import json
import os
import base64
from datetime import datetime, timezone

import requests

from scripts.env import load_dotenv


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def using_supabase():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _jwt_payload(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
    except Exception:
        return {}


def validate_service_role_key():
    role = _jwt_payload(SUPABASE_SERVICE_ROLE_KEY).get("role")
    if role != "service_role":
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY must be your Supabase service_role key. "
            "The anon/public key cannot write scraper rows because Row Level Security blocks inserts."
        )


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def linkedin_time_to_iso(value):
    if value in (None, "", False):
        return None

    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None

    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000

    try:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


class SupabaseClient:
    def __init__(self):
        if not using_supabase():
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
        validate_service_role_key()

        self.base_url = f"{SUPABASE_URL}/rest/v1"
        self.headers = {
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    def _request(self, method, path, *, params=None, payload=None, prefer=None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer

        response = requests.request(
            method,
            f"{self.base_url}/{path}",
            headers=headers,
            params=params,
            data=json.dumps(payload) if payload is not None else None,
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase {method} {path} failed: {response.status_code} {response.text}")
        if response.text:
            return response.json()
        return None

    def select_existing_job_ids(self, job_ids):
        if not job_ids:
            return set()
        params = {
            "select": "job_id",
            "job_id": f"in.({','.join(str(job_id) for job_id in job_ids)})",
        }
        rows = self._request("GET", "jobs", params=params) or []
        return {row["job_id"] for row in rows}

    def select_pending_job_ids(self, limit=None):
        params = {
            "select": "job_id",
            "scraped": "eq.0",
            "order": "job_id.desc",
        }
        if limit:
            params["limit"] = str(limit)
        rows = self._request("GET", "jobs", params=params) or []
        return [row["job_id"] for row in rows]

    def upsert(self, table, rows, on_conflict):
        if not rows:
            return
        self._request(
            "POST",
            table,
            params={"on_conflict": on_conflict},
            payload=rows,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def insert(self, table, rows):
        if not rows:
            return
        self._request("POST", table, payload=rows)

    def update_job(self, job_id, values):
        self._request("PATCH", "jobs", params={"job_id": f"eq.{job_id}"}, payload=values)


def get_supabase_client():
    return SupabaseClient()
