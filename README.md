# LinkedIn Job Scraper

<img src="media/logo.jpg" width="530" height="267">

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

## Supabase + Vercel Deployment

1. Create a Supabase project and run the SQL in `supabase_schema.sql` from the Supabase SQL editor.
2. Copy `.env.example` to `.env` and set `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
3. Update `supabase-config.js` with your Supabase project URL and public anon key. Do not put the service role key in this file.
4. Deploy the repo to Vercel as a static project. `index.html` and `supabase-config.js` are enough for the frontend.
5. The local backend server or CLI scripts will automatically write to Supabase when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are present in `.env`. New jobs get `discovered_at`; detailed jobs get `posted_at` from LinkedIn listing time when LinkedIn provides it, and `scraped_at` when the detail scraper stores the full posting. Logins and active configuration are synced dynamically across SQLite and Supabase.

## Converting Database to CSV

```python to_csv.py --folder <destination folder> --database <linkedin_jobs.db>```

Creates a CSV file for each database, along with minimal preprocessing


## Database Structure

[You can find the structure of the database here](DatabaseStructure.md)
