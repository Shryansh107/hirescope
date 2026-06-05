"""
Dual-backend database access layer for scrape configs and scrape runs.

Every function checks using_supabase() and branches to the appropriate
storage backend (SQLite or Supabase REST).
"""

import json
import sqlite3
import os

from scripts.supabase_client import using_supabase, utc_now_iso

DB_FILE = 'linkedin_jobs.db'

# ── JSON field names that are stored as JSON arrays ──────────────────────
JSON_FIELDS = [
    'keywords', 'job_titles', 'excluded_keywords', 'job_type',
    'experience_level', 'required_skills', 'preferred_skills',
    'programming_languages', 'company_names', 'excluded_companies',
    'company_size', 'industry',
]


def _serialize_config(data: dict) -> dict:
    """Ensure JSON array fields are serialised to strings for SQLite."""
    out = dict(data)
    for field in JSON_FIELDS:
        if field in out and isinstance(out[field], list):
            out[field] = json.dumps(out[field])
    return out


def _deserialize_config(row: dict) -> dict:
    """Parse JSON array strings back to Python lists."""
    out = dict(row)
    for field in JSON_FIELDS:
        val = out.get(field)
        if isinstance(val, str):
            try:
                out[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                out[field] = []
    # Supabase already returns lists for jsonb columns — no extra work
    return out


# ═══════════════════════════════════════════════════════════════════════
# Config CRUD
# ═══════════════════════════════════════════════════════════════════════

def save_config(data: dict) -> int:
    """Create or update a scrape config profile.  Returns the config id."""
    now = utc_now_iso()
    data.setdefault('created_at', now)
    data['updated_at'] = now

    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        config_id = data.get('id')
        if config_id:
            client.update_config(int(config_id), data)
            return int(config_id)
        else:
            return client.insert_config(data)
    else:
        row = _serialize_config(data)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        config_id = row.pop('id', None)
        if config_id:
            cols = ', '.join(f"{k} = ?" for k in row)
            vals = list(row.values()) + [config_id]
            cursor.execute(f"UPDATE scrape_configs SET {cols} WHERE id = ?", vals)
            conn.commit()
            conn.close()
            return int(config_id)
        else:
            columns = list(row.keys())
            placeholders = ', '.join(['?'] * len(columns))
            vals = [row[c] for c in columns]
            cursor.execute(
                f"INSERT INTO scrape_configs ({', '.join(columns)}) VALUES ({placeholders})",
                vals,
            )
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return new_id


def get_config(config_id: int) -> dict | None:
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        return client.select_config(config_id)
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scrape_configs WHERE id = ?", (config_id,))
        row = cursor.fetchone()
        conn.close()
        return _deserialize_config(dict(row)) if row else None


def list_configs() -> list[dict]:
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        return client.select_configs()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scrape_configs ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [_deserialize_config(dict(r)) for r in rows]


def delete_config(config_id: int):
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.delete_config(config_id)
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scrape_configs WHERE id = ?", (config_id,))
        conn.commit()
        conn.close()


def activate_config(config_id: int):
    """Set *only* this config as active."""
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.activate_config(config_id)
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE scrape_configs SET is_active = 0")
        cursor.execute("UPDATE scrape_configs SET is_active = 1 WHERE id = ?", (config_id,))
        conn.commit()
        conn.close()


def get_active_config() -> dict | None:
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        return client.select_active_config()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scrape_configs WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        return _deserialize_config(dict(row)) if row else None


# ═══════════════════════════════════════════════════════════════════════
# Scrape Runs
# ═══════════════════════════════════════════════════════════════════════

def create_run(config_id: int) -> int:
    """Insert a new run with status='running'.  Returns run_id."""
    now = utc_now_iso()
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        return client.insert_run({
            'config_id': config_id,
            'status': 'running',
            'started_at': now,
        })
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO scrape_runs (config_id, status, started_at) VALUES (?, 'running', ?)",
            (config_id, now),
        )
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return run_id


def update_run_progress(run_id: int, **kwargs):
    """Update progress fields on an existing run."""
    if not kwargs:
        return
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.update_run(run_id, kwargs)
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cols = ', '.join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [run_id]
        cursor.execute(f"UPDATE scrape_runs SET {cols} WHERE run_id = ?", vals)
        conn.commit()
        conn.close()


def finish_run(run_id: int, status: str = 'completed'):
    """Mark a run as finished."""
    update_run_progress(run_id, status=status, finished_at=utc_now_iso())


def get_run(run_id: int) -> dict | None:
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        return client.select_run(run_id)
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scrape_runs WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            d = dict(row)
            if isinstance(d.get('error_log'), str):
                try:
                    d['error_log'] = json.loads(d['error_log'])
                except Exception:
                    d['error_log'] = []
            return d
        return None


def get_current_run() -> dict | None:
    """Return the latest run with status 'running' or 'stopping'."""
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        return client.select_current_run()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM scrape_runs WHERE status IN ('running', 'stopping') "
            "ORDER BY run_id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            d = dict(row)
            if isinstance(d.get('error_log'), str):
                try:
                    d['error_log'] = json.loads(d['error_log'])
                except Exception:
                    d['error_log'] = []
            return d
        return None


def list_runs(limit: int = 20) -> list[dict]:
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        return client.select_runs(limit)
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM scrape_runs ORDER BY run_id DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get('error_log'), str):
                try:
                    d['error_log'] = json.loads(d['error_log'])
                except Exception:
                    d['error_log'] = []
            results.append(d)
        return results


def append_run_error(run_id: int, error_msg: str):
    """Append an error message to a run's error_log and increment error count."""
    run = get_run(run_id)
    if not run:
        return
    errors = run.get('error_log', [])
    if not isinstance(errors, list):
        errors = []
    errors.append(error_msg)

    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.update_run(run_id, {
            'error_log': errors,
            'errors': run.get('errors', 0) + 1,
        })
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE scrape_runs SET error_log = ?, errors = ? WHERE run_id = ?",
            (json.dumps(errors), run.get('errors', 0) + 1, run_id),
        )
        conn.commit()
        conn.close()
