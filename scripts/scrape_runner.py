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


def _existing_job_ids(job_ids, cursor):
    """Return existing job ids for the active backend."""
    job_ids = list(job_ids)
    if not job_ids:
        return set()

    if using_supabase():
        from scripts.supabase_client import get_supabase_client
        return get_supabase_client().select_existing_job_ids(job_ids)

    query = "SELECT job_id FROM jobs WHERE job_id IN ({})".format(
        ','.join(['?'] * len(job_ids))
    )
    cursor.execute(query, job_ids)
    return {r[0] for r in cursor.fetchall()}


def run_scrape(run_id: int):
    """
    Continuous scrape execution in a background thread.
    Runs discovery + detail loops indefinitely, sleeping between cycles.
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

    max_pages = config.get('pages_to_scrape', 100)
    update_run_progress(run_id, total_pages=max_pages, status='running')
    print(f"[scrape_runner] Starting continuous run {run_id} — scanning up to {max_pages} pages per cycle")

    # Accumulators for this continuous run
    all_discovered_ids = set()
    total_new_jobs_count = 0
    cycle = 1

    while True:
        if _should_stop(run_id):
            print(f"[scrape_runner] Stop requested before cycle {cycle}")
            break

        print(f"\n[scrape_runner] ===== Starting Cycle {cycle} =====")
        conn, cursor = _get_db()

        # ── Phase 1: Job Discovery ──────────────────────────────────────
        cycle_discovered_ids = set()
        cycle_new_jobs = {}
        pending_insert_jobs = {}

        def flush_pending_jobs(force=False):
            nonlocal total_new_jobs_count
            if not pending_insert_jobs or (not force and len(pending_insert_jobs) < 5):
                return

            batch = dict(pending_insert_jobs)
            insert_job_postings(batch, conn, cursor)
            cycle_new_jobs.update(batch)
            pending_insert_jobs.clear()

            total_new_jobs_count += len(batch)
            update_run_progress(run_id, new_jobs=total_new_jobs_count)
            print(f"[scrape_runner] Inserted {len(batch)} new jobs; total new this run: {total_new_jobs_count}")

        # Parse locations list
        loc_str = config.get('location', '')
        location_list = []
        try:
            if loc_str.startswith('['):
                location_list = json.loads(loc_str)
        except Exception:
            pass

        if not location_list:
            location_list = [{'location': loc_str, 'workplace': [config.get('remote_filter', 'any')]}]

        for loc_item in location_list:
            if _should_stop(run_id):
                break

            loc_name = loc_item.get('location', '')
            workplaces = loc_item.get('workplace', ['any'])

            print(f"[scrape_runner] Scanning location: {loc_name} with workplace types: {workplaces}")

            sub_config = dict(config)
            sub_config['location'] = loc_name
            sub_config['remote_filter'] = workplaces

            try:
                searcher = JobSearchRetriever(config=sub_config)
            except Exception as e:
                append_run_error(run_id, f"Cycle {cycle} session init failed for {loc_name}: {e}")
                print(f"[scrape_runner] Cycle {cycle} session init failed for {loc_name}: {e}")
                time.sleep(5)
                continue

            for page in range(max_pages):
                if _should_stop(run_id):
                    print(f"[scrape_runner] Stop requested at page {page + 1}")
                    break

                try:
                    start_offset = page * 25
                    jobs = searcher.get_jobs(start=start_offset)
                except Exception as e:
                    append_run_error(run_id, f"Search page {page + 1} error for {loc_name}: {e}")
                    print(f"[scrape_runner] Search page {page + 1} error for {loc_name}: {e}")
                    traceback.print_exc()
                    continue

                # Apply config-based filtering on titles
                filtered_jobs = {}
                for job_id, info in jobs.items():
                    if matches_config_filters(info.get('title', ''), config):
                        filtered_jobs[job_id] = info

                cycle_discovered_ids.update(filtered_jobs.keys())
                all_discovered_ids.update(filtered_jobs.keys())

                candidates = {
                    jid: info
                    for jid, info in filtered_jobs.items()
                    if jid not in cycle_new_jobs and jid not in pending_insert_jobs
                }
                existing = _existing_job_ids(candidates.keys(), cursor)
                for job_id, info in candidates.items():
                    if job_id in existing:
                        continue
                    score, matched = compute_relevance(info, config)
                    info['relevance_score'] = score
                    info['matched_keywords'] = json.dumps(matched)
                    info['scrape_run_id'] = run_id
                    pending_insert_jobs[job_id] = info
                    flush_pending_jobs()

                update_run_progress(
                    run_id,
                    pages_scraped=page + 1,
                    total_found=len(all_discovered_ids),
                )
                print(f"[scrape_runner] Cycle {cycle}, {loc_name}, Page {page + 1}: {len(jobs)} raw → {len(filtered_jobs)} filtered, total run discovered: {len(all_discovered_ids)}")

                if not jobs:
                    print(f"[scrape_runner] No more results at page {page + 1} for {loc_name}")
                    break

                time.sleep(1)

        if _should_stop(run_id):
            flush_pending_jobs(force=True)
            if conn: conn.close()
            break

        flush_pending_jobs(force=True)
        print(f"[scrape_runner] Cycle {cycle} discovery: {len(cycle_discovered_ids)} found, {len(cycle_new_jobs)} new")

        # ── Phase 2: Detail Retrieval ───────────────────────────────────
        if _should_stop(run_id):
            if conn: conn.close()
            break

        detail_ids = list(cycle_new_jobs.keys())
        if detail_ids:
            try:
                detail_retriever = JobDetailRetriever()
            except Exception as e:
                append_run_error(run_id, f"Cycle {cycle} detail session init failed: {e}")
                print(f"[scrape_runner] Cycle {cycle} detail session init failed: {e}")
                detail_retriever = None

            if detail_retriever:
                batch_size = 25
                for i in range(0, len(detail_ids), batch_size):
                    if _should_stop(run_id):
                        break

                    batch = detail_ids[i:i + batch_size]
                    try:
                        details = detail_retriever.get_job_details(batch)
                        cleaned = clean_job_postings(details)

                        for job_id, job_info in cleaned.items():
                            if 'error' not in job_info and 'jobs' in job_info:
                                job_flat = dict(job_info.get('jobs', {}))
                                job_flat['title'] = job_flat.get('title', cycle_new_jobs.get(job_id, {}).get('title', ''))
                                score, matched = compute_relevance(job_flat, config)
                                job_info['relevance_score'] = score
                                job_info['matched_keywords'] = json.dumps(matched)

                        insert_data(cleaned, conn, cursor)
                    except Exception as e:
                        append_run_error(run_id, f"Cycle {cycle} detail batch error: {e}")
                        print(f"[scrape_runner] Detail batch error: {e}")
                        traceback.print_exc()

                    time.sleep(1)

        if conn:
            conn.close()

        if _should_stop(run_id):
            break

        # Cooldown wait phase (10 minutes + random jitter)
        cooldown_seconds = 600 + random.randint(-30, 30)
        print(f"[scrape_runner] Cycle {cycle} complete. Sleeping for {cooldown_seconds}s before Cycle {cycle + 1}...")
        
        # Sleep in 5-second increments to stay responsive to stop signals
        for _ in range(0, cooldown_seconds, 5):
            if _should_stop(run_id):
                break
            time.sleep(5)

        cycle += 1

    # Loop terminated — final status update
    final_status = 'stopped' if _should_stop(run_id) else 'completed'
    finish_run(run_id, final_status)
    print(f"[scrape_runner] Continuous run {run_id} finished with status: {final_status}")
