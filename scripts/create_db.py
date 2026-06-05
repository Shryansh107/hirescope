def ensure_column(cursor, table_name, column_name, column_type):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def create_tables(conn, cursor):
    cursor.execute('''
          CREATE TABLE IF NOT EXISTS jobs (
          job_id INTEGER PRIMARY KEY,
          scraped INTEGER NOT NULL DEFAULT 0,
          company_id INTEGER,
          work_type TEXT,
          formatted_work_type TEXT,
          location TEXT,
          job_posting_url TEXT,
          applies INTEGER,
          original_listed_time TEXT,
          remote_allowed INTEGER,
          application_url TEXT,
          application_type TEXT,
          expiry TEXT,
          inferred_benefits TEXT,
          closed_time TEXT,
          formatted_experience_level TEXT,
          years_experience INTEGER,
          description TEXT,
          title TEXT,
          skills_desc TEXT,
          views INTEGER,
          job_region TEXT,
          listed_time TEXT,
          degree TEXT,
          posting_domain TEXT,
          sponsored INTEGER,
          posted_at TEXT,
          scraped_at TEXT,
          discovered_at TEXT,
          relevance_score INTEGER,
          matched_keywords TEXT,
          scrape_run_id INTEGER
        );
    ''')
    ensure_column(cursor, 'jobs', 'posted_at', 'TEXT')
    ensure_column(cursor, 'jobs', 'scraped_at', 'TEXT')
    ensure_column(cursor, 'jobs', 'discovered_at', 'TEXT')
    ensure_column(cursor, 'jobs', 'relevance_score', 'INTEGER')
    ensure_column(cursor, 'jobs', 'matched_keywords', 'TEXT')
    ensure_column(cursor, 'jobs', 'scrape_run_id', 'INTEGER')

    cursor.execute('''
      CREATE TABLE IF NOT EXISTS skills (
          skill_abr TEXT PRIMARY KEY,
          skill_name TEXT
      )
  ''')

    cursor.execute('''
      CREATE TABLE IF NOT EXISTS job_skills (
          job_id INTEGER,
          skill_abr TEXT,
          FOREIGN KEY (job_id) REFERENCES jobs(job_id),
          FOREIGN KEY (skill_abr) REFERENCES skills(skill_abr),
          PRIMARY KEY (job_id, skill_abr)
      )
    ''')

    cursor.execute('''
      CREATE TABLE IF NOT EXISTS industries (
          industry_id INTEGER PRIMARY KEY,
          industry_name TEXT
      )
    ''')

    cursor.execute('''
      CREATE TABLE IF NOT EXISTS job_industries (
          job_id INTEGER,
          industry_id INTEGER,
          FOREIGN KEY (job_id) REFERENCES jobs(job_id),
          FOREIGN KEY (industry_id) REFERENCES industries(industry_id),
          PRIMARY KEY (job_id, industry_id)
      )
    ''')

    cursor.execute('''
      CREATE TABLE IF NOT EXISTS salaries (
          salary_id INTEGER PRIMARY KEY,
          job_id INTEGER NOT NULL,
          max_salary FLOAT,
          med_salary FLOAT,
          min_salary FLOAT,
          pay_period TEXT,
          currency TEXT,
          compensation_type TEXT,
          FOREIGN KEY (job_id) REFERENCES job_postings (job_id)
      )
    ''')

    cursor.execute('''
      CREATE TABLE IF NOT EXISTS benefits (
          job_id INTEGER NOT NULL,
          inferred INTEGER NOT NULL,
          type TEXT NOT NULL,
          FOREIGN KEY (job_id) REFERENCES job_postings (job_id),
          PRIMARY KEY (job_id, type)
      )
    ''')

    # Create the "companies" table

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            company_id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT,
            company_size INTEGER,
            state TEXT,
            country TEXT,
            city TEXT,
            zip_code TEXT,
            address TEXT,
            url TEXT
        )
    ''')

#           record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS employee_counts (
          company_id INTEGER NOT NULL,
          employee_count INTEGER,
          follower_count INTEGER,
          time_recorded INTEGER NOT NULL,
          FOREIGN KEY (company_id) REFERENCES companies (company_id)
          PRIMARY KEY ( employee_count, company_id)
      )
    ''')
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS company_specialities (
          company_id INTEGER NOT NULL,
          speciality INTEGER NOT NULL,
          FOREIGN KEY (company_id) REFERENCES companies (company_id),
          PRIMARY KEY (company_id, speciality)

      )
    ''')


    cursor.execute('''
      CREATE TABLE IF NOT EXISTS company_industries (
          company_id INTEGER NOT NULL,
          industry INTEGER NOT NULL,
          FOREIGN KEY (company_id) REFERENCES companies (company_id),
          PRIMARY KEY (company_id, industry)
      )
    ''')

    # Scrape configuration profiles
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS scrape_configs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_name TEXT NOT NULL,
          keywords TEXT DEFAULT '[]',
          job_titles TEXT DEFAULT '[]',
          excluded_keywords TEXT DEFAULT '[]',
          location TEXT DEFAULT '',
          remote_filter TEXT DEFAULT 'any',
          job_type TEXT DEFAULT '[]',
          experience_level TEXT DEFAULT '[]',
          years_of_experience_min INTEGER,
          years_of_experience_max INTEGER,
          expected_pay_min INTEGER,
          expected_pay_max INTEGER,
          pay_currency TEXT DEFAULT 'USD',
          required_skills TEXT DEFAULT '[]',
          preferred_skills TEXT DEFAULT '[]',
          programming_languages TEXT DEFAULT '[]',
          company_names TEXT DEFAULT '[]',
          excluded_companies TEXT DEFAULT '[]',
          company_size TEXT DEFAULT '[]',
          industry TEXT DEFAULT '[]',
          date_posted TEXT DEFAULT 'any',
          max_jobs_to_scrape INTEGER DEFAULT 100,
          pages_to_scrape INTEGER DEFAULT 10,
          weight_title_match INTEGER DEFAULT 7,
          weight_skills_match INTEGER DEFAULT 7,
          weight_salary_match INTEGER DEFAULT 5,
          is_active INTEGER DEFAULT 0,
          created_at TEXT,
          updated_at TEXT
      )
    ''')

    # Scrape run history
    cursor.execute('''
      CREATE TABLE IF NOT EXISTS scrape_runs (
          run_id INTEGER PRIMARY KEY AUTOINCREMENT,
          config_id INTEGER,
          status TEXT DEFAULT 'pending',
          started_at TEXT,
          finished_at TEXT,
          total_found INTEGER DEFAULT 0,
          new_jobs INTEGER DEFAULT 0,
          pages_scraped INTEGER DEFAULT 0,
          total_pages INTEGER DEFAULT 0,
          errors INTEGER DEFAULT 0,
          error_log TEXT DEFAULT '[]',
          FOREIGN KEY (config_id) REFERENCES scrape_configs(id)
      )
    ''')

    conn.commit()
    return True
