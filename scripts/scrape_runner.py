"""
Scrape runner — orchestrator for dashboard-triggered scrapes.

Called from a background thread by server.py.  Reads the active config,
drives JobSearchRetriever + JobDetailRetriever with config-based filters,
scores every job for relevance, and reports progress into scrape_runs.
"""

import json
import random
import time
import traceback

from scripts.config_db import (
    get_active_config,
    get_run,
    update_run_progress,
    finish_run,
    append_run_error,
)
from scripts.database_scripts import insert_job_postings, insert_data
from scripts.helpers import clean_job_postings, matches_config_filters
from scripts.relevance import compute_relevance
from scripts.supabase_client import using_supabase, utc_now_iso

import sqlite3


def _should_stop(run_id: int) -> bool:
    """Check if the run has been flagged for stopping."""
    run = get_run(run_id)
    return run is not None and run.get('status') in ('stopping', 'stopped')


def _get_db():
    """Return (conn, cursor) for SQLite, or (None, None) for Supabase."""
    if using_supabase():
        return None, None
    conn = sqlite3.connect('linkedin_jobs.db')
    cursor = conn.cursor()
    return conn, cursor


def run_scrape(run_id: int):
    """
    Main scrape execution.  Designed to run in a background thread.

    1. Load config from the run's config_id
    2. Initialise sessions (reuses cached cookies via SessionPool)
    3. Discovery loop — paginate search results
    4. Detail loop — fetch full details for discovered jobs
    5. Score every job for relevance
    6. Update run status to completed/stopped/failed
    """
    from scripts.fetch import JobSearchRetriever, JobDetailRetriever

    run = get_run(run_id)
    if not run:
        print(f"[scrape_runner] Run {run_id} not found")
        return

    config = get_active_config()
    if not config:
        finish_run(run_id, 'failed')
        append_run_error(run_id, "No active scrape config found")
        print("[scrape_runner] No active config — aborting")
        return

    max_pages = config.get('pages_to_scrape', 10)
    max_jobs = config.get('max_jobs_to_scrape', 100)

    update_run_progress(run_id, total_pages=max_pages, status='running')
    print(f"[scrape_runner] Starting run {run_id} — max {max_pages} pages, {max_jobs} jobs")

    conn, cursor = _get_db()

    # ── Phase 1: Job Discovery ──────────────────────────────────────────
    all_discovered = {}  # job_id → basic info dict
    try:
        searcher = JobSearchRetriever(config=config)
    except Exception as e:
        finish_run(run_id, 'failed')
        append_run_error(run_id, f"Session init failed: {e}")
        print(f"[scrape_runner] Session init failed: {e}")
        return

    for page in range(max_pages):
        if _should_stop(run_id):
            print(f"[scrape_runner] Stop requested at page {page + 1}")
            break

        try:
            start_offset = page * 25
            jobs = searcher.get_jobs(start=start_offset)
        except Exception as e:
            append_run_error(run_id, f"Search page {page + 1} error: {e}")
            print(f"[scrape_runner] Search page {page + 1} error: {e}")
            traceback.print_exc()
            continue

        # Apply config-based filtering on titles
        filtered_jobs = {}
        for job_id, info in jobs.items():
            if matches_config_filters(info.get('title', ''), config):
                filtered_jobs[job_id] = info

        all_discovered.update(filtered_jobs)

        update_run_progress(
            run_id,
            pages_scraped=page + 1,
            total_found=len(all_discovered),
        )
        print(f"[scrape_runner] Page {page + 1}: {len(jobs)} raw → {len(filtered_jobs)} filtered, total {len(all_discovered)}")

        if len(all_discovered) >= max_jobs:
            print(f"[scrape_runner] Reached max jobs limit ({max_jobs})")
            break

        if not jobs:
            print(f"[scrape_runner] No more results at page {page + 1}")
            break

        # Small delay between search pages
        time.sleep(1)

    if _should_stop(run_id):
        finish_run(run_id, 'stopped')
        print(f"[scrape_runner] Run {run_id} stopped during discovery")
        return

    # ── Deduplicate against DB ──────────────────────────────────────────
    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        supabase = get_supabase_client()
        existing = supabase.select_existing_job_ids(all_discovered.keys())
    else:
        if all_discovered:
            query = "SELECT job_id FROM jobs WHERE job_id IN ({})".format(
                ','.join(['?'] * len(all_discovered))
            )
            cursor.execute(query, list(all_discovered.keys()))
            existing = {r[0] for r in cursor.fetchall()}
        else:
            existing = set()

    new_jobs = {jid: info for jid, info in all_discovered.items() if jid not in existing}

    # ── Compute preliminary relevance for discovered jobs ───────────────
    for job_id, info in new_jobs.items():
        score, matched = compute_relevance(info, config)
        info['relevance_score'] = score
        info['matched_keywords'] = json.dumps(matched)
        info['scrape_run_id'] = run_id

    # ── Insert discovered jobs ──────────────────────────────────────────
    if new_jobs:
        insert_job_postings(new_jobs, conn, cursor)

    update_run_progress(run_id, new_jobs=len(new_jobs))
    print(f"[scrape_runner] Discovered {len(all_discovered)} total, {len(new_jobs)} new")

    # ── Phase 2: Detail Retrieval ───────────────────────────────────────
    if _should_stop(run_id):
        finish_run(run_id, 'stopped')
        return

    detail_ids = list(new_jobs.keys())
    if not detail_ids:
        finish_run(run_id, 'completed')
        print(f"[scrape_runner] Run {run_id} completed — no new jobs to detail")
        return

    try:
        detail_retriever = JobDetailRetriever()
    except Exception as e:
        append_run_error(run_id, f"Detail session init failed: {e}")
        finish_run(run_id, 'completed')
        print(f"[scrape_runner] Detail session init failed (continuing without details): {e}")
        return

    # Process in batches
    batch_size = 25
    for i in range(0, len(detail_ids), batch_size):
        if _should_stop(run_id):
            print(f"[scrape_runner] Stop requested during detail retrieval")
            break

        batch = detail_ids[i:i + batch_size]
        try:
            details = detail_retriever.get_job_details(batch)
            cleaned = clean_job_postings(details)

            # Compute relevance with full details
            for job_id, job_info in cleaned.items():
                if 'error' not in job_info and 'jobs' in job_info:
                    job_flat = dict(job_info.get('jobs', {}))
                    job_flat['title'] = job_flat.get('title', new_jobs.get(job_id, {}).get('title', ''))
                    score, matched = compute_relevance(job_flat, config)
                    job_info['relevance_score'] = score
                    job_info['matched_keywords'] = json.dumps(matched)

            insert_data(cleaned, conn, cursor)
        except Exception as e:
            append_run_error(run_id, f"Detail batch error: {e}")
            print(f"[scrape_runner] Detail batch error: {e}")
            traceback.print_exc()

        update_run_progress(run_id, total_found=len(all_discovered), new_jobs=len(new_jobs))
        time.sleep(1)

    # ── Finish ──────────────────────────────────────────────────────────
    final_status = 'stopped' if _should_stop(run_id) else 'completed'
    finish_run(run_id, final_status)
    print(f"[scrape_runner] Run {run_id} finished with status: {final_status}")
