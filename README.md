# LinkedIn Job Scraper


**Program to scrape and store a constant stream of LinkedIn job postings and dozens of their respective attributes**

**Download the polished dataset and view insights at - https://www.kaggle.com/datasets/arshkon/linkedin-job-postings**

## User Configurations

### Required
- **```logins.csv```**
  - Populate with one or more LinkedIn logins.
  - A single account can perform both search and detail retrieval (shared via a session pool). No "method" column is needed.

## Running the Web Dashboard (Recommended)

Start the local server to run the scraper via an interactive UI dashboard:
```bash
python server.py
```
Then open `index.html` in your browser. From here you can:
* Save and manage scrape configuration profiles (keywords, exclusions, salary ranges, weights).
* Start, stop, and monitor scrape runs in real-time.
* View details, relevance scores, and matched keywords for all scraped jobs.

## Running via Command Line (Alternative)

This program consists of 2 main scripts, which read the active config from the database:

```python search_retriever.py``` - discovers new job postings and inserts the most recent IDs and minimal attributes into the database.

```python details_retriever.py``` - populates tables with complete job attributes.

## Database Setup & Migrations

The scraper dynamically supports two database backends: local **SQLite** (default) and **Supabase** (Postgres cloud, for deployments).

### SQLite (Local Development)
* Auto-initializes on server start (`linkedin_jobs.db`).
* If you have an older database file or need to upgrade/migrate the schema to the latest version, run:
  ```bash
  python scripts/create_db.py
  ```

### Supabase (Cloud Deployment)
1. **Environment Variables:** Copy `.env.example` to `.env` and set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` to connect the scraper.
2. **Frontend Configuration:** Update `supabase-config.js` with your Supabase project URL and public anon key for the frontend dashboard. (Do not put your service role key here).
3. **Database Schema Upgrades/Migrations:**
   - **For New Deployments:** Execute the SQL queries from `supabase_schema.sql` in the Supabase SQL Editor.
   - **For Existing Deployments (Migrating Older Schema):** Execute the SQL queries from `supabase_migration.sql` in the Supabase SQL Editor.
4. **Hosting:** Deploy the repository to Vercel as a static project (`index.html` and `supabase-config.js` are sufficient). The local scraper backend will automatically sync data to the cloud when environment variables are set.

## Converting Database to CSV

```python to_csv.py --folder <destination folder> --database <linkedin_jobs.db>```

Creates a CSV file for each database, along with minimal preprocessing


## Database Structure

[You can find the structure of the database here](DatabaseStructure.md)
