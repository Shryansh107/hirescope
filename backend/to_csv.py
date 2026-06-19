import sqlite3
import csv
import os
import pandas as pd
import argparse
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.scripts.supabase_client import using_supabase, get_supabase_client

parser = argparse.ArgumentParser()

parser.add_argument('-d', '--database', default=os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'linkedin_jobs.db')))
parser.add_argument('-f', '--folder', default='csv_files')
args = parser.parse_args()

folder_name = args.folder

if not os.path.exists(folder_name):
    os.mkdir(folder_name)

TABLE_NAMES = [
    'jobs', 'salaries', 'companies', 'employee_counts', 'benefits', 
    'skills', 'job_skills', 'industries', 'job_industries', 
    'company_specialities', 'company_industries', 'scrape_configs', 'scrape_runs'
]

DEFAULT_HEADERS = {
    'jobs': ['job_id', 'title', 'sponsored', 'discovered_at', 'scraped', 'company_id', 'posted_at', 'scraped_at', 'location', 'formatted_work_type', 'formatted_experience_level', 'years_experience', 'views', 'applies', 'job_posting_url', 'application_url', 'application_type', 'expiry', 'closed_time', 'skills_desc', 'description'],
    'salaries': ['salary_id', 'job_id', 'max_salary', 'med_salary', 'min_salary', 'pay_period', 'currency', 'compensation_type']
}

if using_supabase():
    print("[+] Exporting tables from Supabase...")
    supabase = get_supabase_client()
    for table_name in TABLE_NAMES:
        rows = supabase.select_table(table_name)
        csv_filename = f'{folder_name}/{table_name}.csv'
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csv_file:
            if rows:
                column_names = list(rows[0].keys())
                csv_writer = csv.DictWriter(csv_file, fieldnames=column_names)
                csv_writer.writeheader()
                csv_writer.writerows(rows)
            else:
                # Write default headers if available, otherwise write empty file
                headers = DEFAULT_HEADERS.get(table_name, [])
                csv_writer = csv.writer(csv_file)
                csv_writer.writerow(headers)
else:
    # Connect to the SQLite database
    print(f"[+] Exporting tables from SQLite database '{args.database}'...")
    conn = sqlite3.connect(args.database)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

    # Fetch all results
    table_names = [x[0] for x in cursor.fetchall()]

    print(table_names)

    for table_name in table_names:
      # Execute a query to fetch all rows from the table
      query = f'SELECT * FROM {table_name}'
      cursor.execute(query)
      rows = cursor.fetchall()

      csv_filename = f'{folder_name}/{table_name}.csv'

      # Write the data to the CSV file
      with open(csv_filename, 'w', newline='', encoding='utf-8') as csv_file:
          csv_writer = csv.writer(csv_file)

          # Write header row with column names
          column_names = [description[0] for description in cursor.description]
          csv_writer.writerow(column_names)

          # Write data rows
          csv_writer.writerows(rows)

    # Close the connection
    conn.close()

# Read and merge jobs & salaries
jobs_csv = f'{folder_name}/jobs.csv'
salaries_csv = f'{folder_name}/salaries.csv'

if os.path.exists(jobs_csv) and os.path.exists(salaries_csv):
    jobs = pd.read_csv(jobs_csv)
    jobs = jobs[jobs['scraped'] > 0]

    salaries = pd.read_csv(salaries_csv)
    if 'salary_id' in salaries.columns:
        salaries.drop(columns='salary_id', inplace=True)

    merged_df = pd.merge(jobs, salaries, on='job_id', how='left')

    col = ['job_id', 'company_id', 'title', 'description', 'max_salary', 'med_salary', 'min_salary', 'pay_period',
           'formatted_work_type', 'location',
           'applies', 'original_listed_time', 'remote_allowed', 'views','job_posting_url',
           'application_url', 'application_type', 'expiry',
           'closed_time', 'formatted_experience_level',
           'skills_desc',
           'listed_time', 'posting_domain', 'sponsored', 'work_type',
           'currency',
           'compensation_type', 'scraped']

    # Ensure all columns exist in merged_df
    for c in col:
        if c not in merged_df.columns:
            merged_df[c] = None

    merged_df = merged_df[col]
    merged_df.to_csv(f'{folder_name}/job_postings.csv', index=False)
    os.remove(jobs_csv)
    print(f"[+] Created merged dataset at '{folder_name}/job_postings.csv'")
else:
    print("[-] Skip merging: jobs.csv or salaries.csv not found.")
