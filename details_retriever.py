from scripts.create_db import create_tables
from scripts.database_scripts import insert_data
from scripts.fetch import JobDetailRetriever
import sqlite3
from scripts.helpers import clean_job_postings
from scripts.config_db import get_active_config
from scripts.relevance import compute_relevance
from scripts.supabase_client import get_supabase_client, using_supabase
import json
import time
import random

SLEEP_TIME = 60
MAX_UPDATES = 25

if using_supabase():
    conn = None
    cursor = None
    supabase = get_supabase_client()
else:
    conn = sqlite3.connect('linkedin_jobs.db')
    cursor = conn.cursor()
    create_tables(conn, cursor)

# Load active config for relevance scoring
config = get_active_config()
if config:
    print(f'[+] Using active config for relevance scoring: "{config.get("profile_name", "unnamed")}"')

job_detail_retriever = JobDetailRetriever()

while True:
    if using_supabase():
        result = supabase.select_pending_job_ids()
    else:
        query = "SELECT job_id FROM jobs WHERE scraped = 0"
        cursor.execute(query)
        result = cursor.fetchall()
        result = [r[0] for r in result]

    details = job_detail_retriever.get_job_details(random.sample(result, min(MAX_UPDATES, len(result))))
    details = clean_job_postings(details)

    # Compute relevance scores if config is available
    if config:
        for job_id, job_info in details.items():
            if 'error' not in job_info and 'jobs' in job_info:
                job_flat = dict(job_info.get('jobs', {}))
                score, matched = compute_relevance(job_flat, config)
                job_info['relevance_score'] = score
                job_info['matched_keywords'] = json.dumps(matched)

    insert_data(details, conn, cursor)
    print('UPDATED {} VALUES IN DB'.format(len(details)))

    print('Sleeping For {} Seconds...'.format(SLEEP_TIME))
    time.sleep(SLEEP_TIME)
    print('Resuming...')
