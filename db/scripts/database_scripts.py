import time
import json
import os

from BE.scripts.supabase_client import get_supabase_client, linkedin_time_to_iso, using_supabase, utc_now_iso


def load_excluded_companies():
    path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'BE', 'excluded_companies.json'))
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return [c.strip().lower() for c in json.load(f) if c]
        except Exception as e:
            print(f"Error loading excluded_companies.json: {e}")
    return []


def _job_posted_at(job_values):
    return linkedin_time_to_iso(job_values.get("listed_time") or job_values.get("original_listed_time"))


def insert_data_supabase(data):
    client = get_supabase_client()
    excluded = load_excluded_companies()

    for job_id, job_info in data.items():
        if "error" in job_info:
            client.update_job(job_id, {"scraped": -1})
            continue

        company_name = job_info.get("companies", {}).get("name")
        if company_name and company_name.strip().lower() in excluded:
            print(f"[-] Excluding job {job_id} from company: {company_name}")
            client.update_job(job_id, {"scraped": -2})
            continue

        company_id = job_info["jobs"].get("company_id")

        companies = job_info.get("companies", {})
        if companies and company_id is not None:
            client.upsert("companies", [{"company_id": company_id, **companies}], "company_id")

        jobs = job_info.get("jobs", {})
        if jobs:
            now = utc_now_iso()
            update_fields = {
                **jobs,
                "scraped": round(time.time()),
                "scraped_at": now,
                "posted_at": _job_posted_at(jobs),
            }
            # Include relevance data if available
            if 'relevance_score' in job_info:
                update_fields['relevance_score'] = job_info['relevance_score']
            if 'matched_keywords' in job_info:
                update_fields['matched_keywords'] = job_info['matched_keywords']
            client.update_job(job_id, update_fields)

        benefits = job_info.get("benefits", {})
        benefit_rows = []
        for benefit in benefits.get("listed_benefits", []):
            benefit_rows.append({"job_id": job_id, "inferred": 0, "type": benefit})
        for benefit in benefits.get("inferred_benefits", []):
            benefit_rows.append({"job_id": job_id, "inferred": 1, "type": benefit})
        client.upsert("benefits", benefit_rows, "job_id,type")

        industries = job_info.get("industries", {})
        industry_rows = []
        job_industry_rows = []
        industry_ids = industries.get("industry_ids", [])
        industry_names = industries.get("industry_names", [])
        for index, industry_id in enumerate(industry_ids):
            industry_name = industry_names[index] if len(industry_names) == len(industry_ids) else None
            industry_rows.append({"industry_id": industry_id, "industry_name": industry_name})
            job_industry_rows.append({"job_id": job_id, "industry_id": industry_id})
        client.upsert("industries", industry_rows, "industry_id")
        client.upsert("job_industries", job_industry_rows, "job_id,industry_id")

        skills = job_info.get("skills", {})
        skill_rows = []
        job_skill_rows = []
        skill_abrs = skills.get("skill_abrs", [])
        skill_names = skills.get("skill_name", [])
        for index, skill_abr in enumerate(skill_abrs):
            skill_name = skill_names[index] if len(skill_names) == len(skill_abrs) else None
            skill_rows.append({"skill_abr": skill_abr, "skill_name": skill_name})
            job_skill_rows.append({"job_id": job_id, "skill_abr": skill_abr})
        client.upsert("skills", skill_rows, "skill_abr")
        client.upsert("job_skills", job_skill_rows, "job_id,skill_abr")

        salary_rows = []
        for compensation_type, values in job_info.get("salaries", {}).items():
            for compensation in values:
                salary_rows.append({
                    "job_id": job_id,
                    "max_salary": compensation.get("maxSalary"),
                    "med_salary": compensation.get("medianSalary"),
                    "min_salary": compensation.get("minSalary"),
                    "pay_period": compensation.get("payPeriod"),
                    "currency": compensation.get("currencyCode"),
                    "compensation_type": compensation.get("compensationType", compensation_type),
                })
        client.insert("salaries", salary_rows)

        employee_counts = job_info.get("employee_counts", {})
        if employee_counts and company_id is not None:
            client.upsert("employee_counts", [{
                "company_id": company_id,
                "employee_count": employee_counts.get("employee_count"),
                "follower_count": employee_counts.get("follower_count"),
                "time_recorded": round(time.time()),
            }], "employee_count,company_id")

        company_industries = [
            {"company_id": company_id, "industry": industry}
            for industry in job_info.get("company_industries", {}).get("industries", [])
            if company_id is not None
        ]
        client.upsert("company_industries", company_industries, "company_id,industry")

        company_specialities = [
            {"company_id": company_id, "speciality": speciality}
            for speciality in job_info.get("company_specialities", {}).get("specialities", [])
            if company_id is not None
        ]
        client.upsert("company_specialities", company_specialities, "company_id,speciality")

    return True


def insert_data(data, conn, cursor):
    if using_supabase():
        return insert_data_supabase(data)

    excluded = load_excluded_companies()
    for job_id, job_info in data.items():
        if 'error' in job_info:
            cursor.execute(f"UPDATE jobs SET scraped = -1 WHERE job_id = ?", (job_id,))
            continue
        
        # Check if the company is in the excluded list
        company_name = job_info.get('companies', {}).get('name')
        if company_name and company_name.strip().lower() in excluded:
            print(f"[-] Excluding job {job_id} from company: {company_name}")
            cursor.execute("UPDATE jobs SET scraped = -2 WHERE job_id = ?", (job_id,))
            continue

        company_id = job_info['jobs'].get('company_id')
        for table_name in job_info:
            # Skip non-table keys
            if table_name in ('relevance_score', 'matched_keywords'):
                continue
            if not isinstance(job_info[table_name], dict) or len(job_info[table_name]) == 0:
                continue

            if table_name == 'jobs':
                posted_at = _job_posted_at(job_info[table_name])
                column_names = list(job_info[table_name].keys())
                values = tuple(job_info[table_name][column] for column in column_names)
                set_clause = ", ".join([f"{column} = ?" for column in column_names])
                set_clause += ", scraped = ?, scraped_at = ?, posted_at = ?"

                # Include relevance data if available
                extra_cols = ""
                extra_vals = ()
                if 'relevance_score' in job_info:
                    extra_cols += ", relevance_score = ?"
                    extra_vals += (job_info['relevance_score'],)
                if 'matched_keywords' in job_info:
                    extra_cols += ", matched_keywords = ?"
                    extra_vals += (job_info['matched_keywords'],)

                set_clause += extra_cols
                values_for_update = values + (round(time.time()), utc_now_iso(), posted_at) + extra_vals + (job_id,)
                query = f"UPDATE {table_name} SET {set_clause} WHERE job_id = ?"
                cursor.execute(query, values_for_update)

            elif table_name == 'benefits':
                if 'listed_benefits' in job_info[table_name]:
                    for benefit in job_info[table_name]['listed_benefits']:
                        cursor.execute(
                            f'INSERT OR REPLACE INTO {table_name} (job_id, inferred, type) VALUES (?, ?, ?)',
                            (job_id, 0, benefit))
                if 'inferred_benefits' in job_info[table_name]:
                    for benefit in job_info[table_name]['inferred_benefits']:
                        cursor.execute(
                            f'INSERT OR IGNORE INTO {table_name} (job_id, inferred, type) VALUES (?, ?, ?)',
                            (job_id, 1, benefit))

            elif table_name == 'industries' and 'industry_ids' in job_info[table_name]:
                for industry_index in range(len(job_info[table_name]['industry_ids'])):
                    industry_id = job_info[table_name]['industry_ids'][industry_index]
                    industry_name = job_info[table_name]['industry_names'][industry_index] if 'industry_names' in job_info[table_name] and len(job_info[table_name]['industry_names']) == len(job_info[table_name]['industry_ids']) else None

                    cursor.execute(
                        'INSERT OR REPLACE INTO industries (industry_id, industry_name) VALUES (?, COALESCE((SELECT industry_name FROM industries WHERE industry_id=?), ?))',
                        (industry_id, industry_id, industry_name))
                    cursor.execute('INSERT OR IGNORE INTO job_industries (job_id, industry_id) VALUES (?, ?)',
                                   (job_id, industry_id))


            elif table_name == 'skills' and 'skill_abrs' in job_info[table_name]:
                for industry_index in range(len(job_info[table_name]['skill_abrs'])):
                    skill_abr = job_info[table_name]['skill_abrs'][industry_index]
                    skill_name = job_info[table_name]['skill_name'][industry_index] if 'skill_name' in job_info[table_name] and len(job_info[table_name]['skill_name']) == len(job_info[table_name]['skill_abrs']) else None
                    cursor.execute(
                        'INSERT OR REPLACE INTO skills (skill_abr, skill_name) VALUES (?, COALESCE((SELECT skill_name FROM skills WHERE skill_abr=?), ?))',
                        (skill_abr, skill_abr, skill_name))
                    cursor.execute('INSERT OR IGNORE INTO job_skills (job_id, skill_abr) VALUES (?, ?)', (job_id, skill_abr))

            elif table_name == 'salaries':
                for compensation_type, values in job_info[table_name].items():
                    for compensation in values:
                        cursor.execute(
                            'INSERT INTO salaries (job_id, max_salary, med_salary, min_salary, pay_period, currency, compensation_type) VALUES (?, ?, ?, ?, ?, ?, ?)',
                            (
                                job_id, compensation.get('maxSalary'), compensation.get('medianSalary'), compensation.get('minSalary'),
                                compensation['payPeriod'],
                                compensation['currencyCode'], compensation['compensationType']))

            elif table_name == 'companies' and company_id is not None:
                column_names = list(job_info[table_name].keys())
                values = tuple(job_info[table_name][column] for column in column_names)
                query = f"INSERT OR REPLACE INTO {table_name} (company_id, {', '.join(column_names)}) VALUES ({company_id}, {', '.join(['?'] * len(column_names))})"
                cursor.execute(query, values)

            elif table_name == 'employee_counts' and company_id is not None:
                cursor.execute(f"INSERT OR IGNORE INTO {table_name} (company_id, employee_count, follower_count, time_recorded) VALUES (?, ?, ?, ?)", (company_id, job_info[table_name]['employee_count'], job_info[table_name]['follower_count'], round(time.time())))

            elif table_name == 'company_industries' and company_id is not None:
                for industry in job_info[table_name]['industries']:
                    cursor.execute(f'INSERT OR IGNORE INTO {table_name} (company_id, industry) VALUES (?, ?)', (company_id, industry))

            elif table_name == 'company_specialities' and company_id is not None:
                for speciality in job_info[table_name]['specialities']:
                    cursor.execute(f'INSERT OR IGNORE INTO {table_name} (company_id, speciality) VALUES (?, ?)', (company_id, speciality))

    conn.commit()
    return True


def insert_job_postings(job_ids, conn, cursor):
    """Insert newly discovered jobs with optional relevance data."""
    if using_supabase():
        client = get_supabase_client()
        rows = []
        now = utc_now_iso()
        for job_id, info in job_ids.items():
            row = {
                "job_id": job_id,
                "title": info["title"],
                "sponsored": info["sponsored"],
                "discovered_at": now,
            }
            if 'relevance_score' in info:
                row['relevance_score'] = info['relevance_score']
            if 'matched_keywords' in info:
                row['matched_keywords'] = info['matched_keywords']
            if 'scrape_run_id' in info:
                row['scrape_run_id'] = info['scrape_run_id']
            rows.append(row)
        client.upsert("jobs", rows, "job_id")
        return True

    for job_id, info in job_ids.items():
        # Build column list dynamically based on what's available
        columns = ['job_id', 'title', 'sponsored', 'discovered_at']
        values = [job_id, info['title'], info['sponsored'], utc_now_iso()]

        if 'relevance_score' in info:
            columns.append('relevance_score')
            values.append(info['relevance_score'])
        if 'matched_keywords' in info:
            columns.append('matched_keywords')
            values.append(info['matched_keywords'])
        if 'scrape_run_id' in info:
            columns.append('scrape_run_id')
            values.append(info['scrape_run_id'])

        placeholders = ', '.join(['?'] * len(columns))
        cursor.execute(
            f'INSERT OR IGNORE INTO jobs ({", ".join(columns)}) VALUES ({placeholders})',
            values,
        )
    conn.commit()
    return True
