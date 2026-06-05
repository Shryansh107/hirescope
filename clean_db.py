import sqlite3
from scripts.fetch import is_valid_sde_job

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
            
        cursor.execute("SELECT job_id, title FROM jobs;")
        jobs = cursor.fetchall()
        
        deleted_count = 0
        for job_id, title in jobs:
            if not is_valid_sde_job(title):
                print(f"[-] Deleting non-SDE/Senior job {job_id}: {title}")
                
                # Delete from all related tables
                cursor.execute("DELETE FROM jobs WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM job_skills WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM job_industries WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM salaries WHERE job_id = ?;", (job_id,))
                cursor.execute("DELETE FROM benefits WHERE job_id = ?;", (job_id,))
                
                deleted_count += 1
                
        conn.commit()
        conn.close()
        print(f"\n[+] Clean-up complete! Removed {deleted_count} non-SDE or senior/business jobs from '{DB_FILE}'.")
        
    except Exception as e:
        print(f"Error cleaning database: {str(e)}")

if __name__ == '__main__':
    clean_database()
