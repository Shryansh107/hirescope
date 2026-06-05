import sqlite3
from scripts.config_db import get_active_config
from scripts.helpers import matches_config_filters

DB_FILE = 'linkedin_jobs.db'

def clean_database():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Check if the jobs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
        if not cursor.fetchone():
            print("No jobs table found in database. Nothing to clean.")
            conn.close()
            return
        
        # Load active config for filtering rules
        config = get_active_config()
        if not config:
            print("[!] No active scrape config found. Skipping clean (no filter rules to apply).")
            conn.close()
            return

        print(f'[+] Using config: "{config.get("profile_name", "unnamed")}"')

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
