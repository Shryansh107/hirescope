# LinkedIn Job Scraper Setup & Execution Guide

This document outlines the step-by-step process to set up, configure, and run the LinkedIn Job Scraper.

---

## 1. Prerequisites

Make sure you have the following installed on your machine:
* **Python 3.8+**
* **Pip** (Python package installer)
* A desktop web browser: **Microsoft Edge** (default) or **Google Chrome**

---

## 2. Setting Up the Environment

1. **(Optional but recommended) Create a Virtual Environment:**
   Run the following commands in your terminal to create and activate a clean Python environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies:**
   Install the required libraries listed in `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

---

## 3. Configuring LinkedIn Credentials

The scraper reads credentials from `logins.csv`. Since a template is provided:

1. **Copy the template file to create `logins.csv`:**
   ```bash
   cp logins.csv.template logins.csv
   ```

2. **Open `logins.csv` and add your account details:**
   * **emails**: The email addresses for your LinkedIn accounts.
   * **passwords**: The passwords corresponding to those accounts.

   > [!NOTE]
   > * A single account can now handle both search and detail retrieval. You do not need to duplicate credentials or specify a "method" column.
   > * You can add multiple accounts to form a shared session pool, which helps bypass LinkedIn's rate limits by rotation.

---

## 4. Selecting Your Browser Engine

By default, the script is configured to use **Microsoft Edge**. If you prefer to use **Google Chrome**:

1. Open [scripts/fetch.py](file:///home/shryansh/directory/projects/LinkedIn-Job-Scraper/scripts/fetch.py) in your editor.
2. Locate line 11:
   ```python
   BROWSER = 'edge'
   ```
3. Change it to:
   ```python
   BROWSER = 'chrome'
   ```

*(Note: Selenium will automatically download and manage the respective browser driver backend as long as the browser itself is installed on your system).*

---

## 5. Running via Web Dashboard (Recommended)

The easiest and most feature-rich way to run the scraper, configure filters, and view results is via the dashboard server:

1. **Start the backend server:**
   ```bash
   python server.py
   ```
2. **Open the frontend in your browser:**
   Open `index.html` in your web browser (or serve it using a local HTTP server).
3. **Configure scraping parameters:**
   Use the UI sidebar to customize keywords, job titles, exclusions, locations, salaries, etc.
4. **Trigger a run:**
   Click **"Start Scraping"** on the dashboard. The server will run the scraper in a background thread and stream progress in real-time.

---

## 6. Running via Command Line (Alternative)

If you prefer to run the scraper directly from the command line:

### Step A: Start the Search Retriever (Discovers Job Listings)
Run this script to find new job postings and insert the initial IDs and basic fields into the database:
```bash
python search_retriever.py
```

### Step B: Start the Details Retriever (Enriches Job Attributes)
Run this script to fetch details (salary, description, benefits, etc.) for the discovered job listings:
```bash
python details_retriever.py
```

---

## 7. Interactive Login & Captcha Phase

Whether running via Web Dashboard or Command Line, when the scraper logs in for the first time:
1. Selenium will open a browser window and navigate to the LinkedIn login page.
2. It will auto-fill your credentials and attempt to log in.
3. If LinkedIn prompts you for a captcha (security verification) or a verification code, complete it manually in the opened browser.
4. Once you are successfully logged in, return to the terminal where the script/server is running.
5. You will see the prompt:
   ```text
   Press ENTER after a successful login for "your-email@example.com":
   ```
   Press **`ENTER`** in that terminal to allow the script to save cookies and continue. Subsequent runs will use the saved cookies without opening a browser window.

---

## 8. Converting the Database to CSV

Once the scraper has populated the database, you can export the collected data to formatted CSV files:

```bash
python to_csv.py --folder csv_output --database linkedin_jobs.db
```

This will create `csv_output/job_postings.csv` containing a fully compiled and merged dataset.
