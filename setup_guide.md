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
   * **method**: Use `search` for accounts that perform job searches, and `details` for accounts that retrieve individual job descriptions and details. 
   
   > [!IMPORTANT]
   > * You must have at least one account mapped to `search` and at least one mapped to `details`.
   > * If you only have **one** LinkedIn account, you can duplicate its details across two lines, specifying `search` for one and `details` for the other.

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

## 5. Running the Scraper

The scraper consists of two main programs designed to run in parallel:

### Step A: Start the Search Retriever (Discovers Job Listings)
Run this script to find new job postings and insert the initial IDs and basic fields into the database:
```bash
python search_retriever.py
```

### Step B: Start the Details Retriever (Enriches Job Attributes)
In a **separate terminal window** (with your virtual environment activated, if applicable), run this script to fetch details (salary, description, benefits, etc.) for the discovered job listings:
```bash
python details_retriever.py
```

### Crucial Step: The Interactive Login Phase
When each script launches for the first time:
1. Selenium will open a browser window and navigate to the LinkedIn login page.
2. It will auto-fill your credentials and attempt to log in.
3. If LinkedIn prompts you for a captcha (security verification) or a verification code, complete it manually in the opened browser.
4. Once you are successfully logged in and view the search/feed page, return to your terminal.
5. You will see the prompt:
   ```text
   Press ENTER after a successful login for "your-email@example.com":
   ```
   Press **`ENTER`** in the terminal to allow the script to save cookies and start the background API calls.

---

## 6. Converting the Database to CSV

Once the scraper has run for a while and populated the SQLite database `linkedin_jobs.db`, you can export the collected data to formatted CSV files:

Run the following command:
```bash
python to_csv.py --folder csv_output --database linkedin_jobs.db
```

This will create a directory called `csv_output/` containing a fully compiled and merged dataset: `job_postings.csv`.
