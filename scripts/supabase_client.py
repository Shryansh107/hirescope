import json
import os
import base64
from datetime import datetime, timezone

import requests

from scripts.env import load_dotenv


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

INTEGER_COLUMNS = {
    "benefits": {"inferred"},
    "companies": {"company_size"},
    "employee_counts": {"employee_count", "follower_count", "time_recorded"},
    "industries": {"industry_id"},
    "job_industries": {"job_id", "industry_id"},
    "job_skills": {"job_id"},
    "jobs": {"job_id", "scraped", "company_id", "applies", "remote_allowed", "years_experience", "views", "relevance_score", "scrape_run_id"},
    "salaries": {"job_id"},
    "scrape_configs": {"id", "years_of_experience_min", "years_of_experience_max", "expected_pay_min", "expected_pay_max", "max_jobs_to_scrape", "pages_to_scrape", "weight_title_match", "weight_skills_match", "weight_salary_match"},
    "scrape_runs": {"run_id", "config_id", "total_found", "new_jobs", "pages_scraped", "total_pages", "errors"},
}


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

    # ── Jobs ────────────────────────────────────────────────────────────
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
        rows = _dedupe_rows(rows, on_conflict)
        rows = _coerce_rows(table, rows)
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
        rows = _coerce_rows(table, rows)
        self._request("POST", table, payload=rows)

    def update_job(self, job_id, values):
        values = _coerce_row("jobs", values)
        self._request("PATCH", "jobs", params={"job_id": f"eq.{job_id}"}, payload=values)

    # ── Scrape Configs ──────────────────────────────────────────────────
    def select_configs(self):
        rows = self._request("GET", "scrape_configs", params={
            "select": "*",
            "order": "updated_at.desc",
        }) or []
        return rows

    def select_config(self, config_id):
        rows = self._request("GET", "scrape_configs", params={
            "select": "*",
            "id": f"eq.{config_id}",
            "limit": "1",
        }) or []
        return rows[0] if rows else None

    def select_active_config(self):
        rows = self._request("GET", "scrape_configs", params={
            "select": "*",
            "is_active": "eq.true",
            "limit": "1",
        }) or []
        return rows[0] if rows else None

    def insert_config(self, data):
        """Insert a new config and return its id."""
        data = _coerce_row("scrape_configs", data)
        data.pop('id', None)
        rows = self._request(
            "POST", "scrape_configs",
            payload=[data],
            prefer="return=representation",
        )
        return rows[0]["id"] if rows else None

    def update_config(self, config_id, data):
        data = _coerce_row("scrape_configs", data)
        data.pop('id', None)
        self._request(
            "PATCH", "scrape_configs",
            params={"id": f"eq.{config_id}"},
            payload=data,
        )

    def delete_config(self, config_id):
        self._request("DELETE", "scrape_configs", params={"id": f"eq.{config_id}"})

    def activate_config(self, config_id):
        """Deactivate all configs, then activate the target."""
        self._request(
            "PATCH", "scrape_configs",
            params={"is_active": "eq.true"},
            payload={"is_active": False},
        )
        self._request(
            "PATCH", "scrape_configs",
            params={"id": f"eq.{config_id}"},
            payload={"is_active": True},
        )

    # ── Scrape Runs ─────────────────────────────────────────────────────
    def insert_run(self, data):
        """Insert a new scrape run and return its run_id."""
        data = _coerce_row("scrape_runs", data)
        rows = self._request(
            "POST", "scrape_runs",
            payload=[data],
            prefer="return=representation",
        )
        return rows[0]["run_id"] if rows else None

    def update_run(self, run_id, data):
        data = _coerce_row("scrape_runs", data)
        self._request(
            "PATCH", "scrape_runs",
            params={"run_id": f"eq.{run_id}"},
            payload=data,
        )

    def select_run(self, run_id):
        rows = self._request("GET", "scrape_runs", params={
            "select": "*",
            "run_id": f"eq.{run_id}",
            "limit": "1",
        }) or []
        return rows[0] if rows else None

    def select_current_run(self):
        rows = self._request("GET", "scrape_runs", params={
            "select": "*",
            "status": "in.(running,stopping)",
            "order": "run_id.desc",
            "limit": "1",
        }) or []
        return rows[0] if rows else None

    def cleanup_stale_runs(self):
        self._request(
            "PATCH", "scrape_runs",
            params={"status": "in.(running,stopping)"},
            payload={"status": "failed"},
        )

    def select_runs(self, limit=20):
        rows = self._request("GET", "scrape_runs", params={
            "select": "*",
            "order": "run_id.desc",
            "limit": str(limit),
        }) or []
        return rows


def get_supabase_client():
    return SupabaseClient()


def _dedupe_rows(rows, on_conflict):
    conflict_columns = [column.strip() for column in on_conflict.split(",") if column.strip()]
    if not conflict_columns:
        return rows

    deduped = {}
    for row in rows:
        key = tuple(row.get(column) for column in conflict_columns)
        deduped[key] = row
    return list(deduped.values())


def _coerce_rows(table, rows):
    return [_coerce_row(table, row) for row in rows]


def _coerce_row(table, row):
    integer_columns = INTEGER_COLUMNS.get(table, set())
    if not integer_columns:
        return row

    coerced = dict(row)
    for column in integer_columns:
        if isinstance(coerced.get(column), bool):
            coerced[column] = int(coerced[column])
    return coerced
