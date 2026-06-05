from scripts.create_db import create_tables
from scripts.database_scripts import insert_job_postings
from scripts.fetch import JobSearchRetriever, SessionPool
from scripts.config_db import get_active_config
from scripts.helpers import matches_config_filters
from scripts.relevance import compute_relevance
from scripts.supabase_client import get_supabase_client, using_supabase
import sqlite3
import json
import time
from collections import deque


sleep_times = deque(maxlen=5)
first = True
sleep_factor = 3

if using_supabase():
    conn = None
    cursor = None
    supabase = get_supabase_client()
else:
    conn = sqlite3.connect('linkedin_jobs.db')
    cursor = conn.cursor()
    create_tables(conn, cursor)

# Load active config if available
config = get_active_config()
if config:
    print(f'[+] Using active config: "{config.get("profile_name", "unnamed")}"')
else:
    print('[!] No active scrape config found — running with no filters')

job_searcher = JobSearchRetriever(config=config)

while True:
    all_results = job_searcher.get_jobs()

    if using_supabase():
        result = supabase.select_existing_job_ids(all_results.keys())
    else:
        if all_results:
            query = "SELECT job_id FROM jobs WHERE job_id IN ({})".format(','.join(['?'] * len(all_results)))
            cursor.execute(query, list(all_results.keys()))
            result = cursor.fetchall()
            result = [r[0] for r in result]
        else:
            result = []

    new_results = {job_id: job_info for job_id, job_info in all_results.items() if job_id not in result}

    # Apply config-based filtering if config exists
    if config:
        filtered_results = {}
        for job_id, job_info in new_results.items():
            if matches_config_filters(job_info.get('title', ''), config):
                # Compute preliminary relevance score
                score, matched = compute_relevance(job_info, config)
                job_info['relevance_score'] = score
                job_info['matched_keywords'] = json.dumps(matched)
                filtered_results[job_id] = job_info
        new_results = filtered_results

    insert_job_postings(new_results, conn, cursor)
    total_non_sponsored = len([x for x in all_results.values() if x['sponsored'] is False])
    new_non_sponsored = len([x for x in new_results.values() if x['sponsored'] is False])
    print('{}/{} NEW RESULTS | {}/{} NEW NON-PROMOTED RESULTS'.format(
        len(new_results), len(all_results), new_non_sponsored, total_non_sponsored))
    if not first:
        seconds_per_job = sleep_factor/max(len(new_results), 1)
        sleep_factor = min(seconds_per_job * total_non_sponsored * .75, 200)
    first = False

    print('Sleeping For {} Seconds...'.format(min(200, sleep_factor)))
    time.sleep(min(200, sleep_factor))
    print('Resuming...')
