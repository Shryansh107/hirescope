import sqlite3
from scripts.config_db import get_active_config
from scripts.helpers import matches_config_filters
from scripts.supabase_client import using_supabase, get_supabase_client

DB_FILE = 'linkedin_jobs.db'

def clean_database():
    try:
        # Load active config for filtering rules
        config = get_active_config()
        if not config:
            print("[!] No active scrape config found. Skipping clean (no filter rules to apply).")
            return

        print(f'[+] Using config: "{config.get("profile_name", "unnamed")}"')

        if using_supabase():
            supabase = get_supabase_client()
            jobs = supabase.select_jobs()
            
            deleted_count = 0
            for job in jobs:
                job_id = job.get('job_id')
                title = job.get('title')
                if job_id and title and not matches_config_filters(title, config):
                    print(f"[-] Deleting non-matching job {job_id}: {title}")
                    # Delete from Supabase. Cascade deletes handle child tables automatically.
                    supabase._request("DELETE", "jobs", params={"job_id": f"eq.{job_id}"})
                    deleted_count += 1
            print(f"\n[+] Clean-up complete! Removed {deleted_count} non-matching jobs from Supabase.")
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if the jobs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
        if not cursor.fetchone():
            print("No jobs table found in database. Nothing to clean.")
            conn.close()
            return
        
        cursor.execute("SELECT job_id, title FROM jobs;")
        jobs = cursor.fetchall()
        
        deleted_count = 0
        for job_id, title in jobs:
            if not matches_config_filters(title, config):
                print(f"[-] Deleting non-matching job {job_id}: {title}")
                
                # Delete from all related tables
                cursor.execute("DELETE FROM jobs WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM job_skills WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM job_industries WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM salaries WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM benefits WHERE job_id = ?;", (job_id,))
                
                deleted_count += 1
                
        conn.commit()
        conn.close()
        print(f"\n[+] Clean-up complete! Removed {deleted_count} non-matching jobs from '{DB_FILE}'.")
        
    except Exception as e:
        print(f"Error cleaning database: {str(e)}")

if __name__ == '__main__':
    clean_database()
