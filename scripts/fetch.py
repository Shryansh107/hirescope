import random
import os
import json
import hashlib
import time
import requests
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scripts.helpers import strip_val, get_value_by_path


# ── Browser config ──────────────────────────────────────────────────────
BROWSER = 'chrome'

# ── Cookie cache directory ──────────────────────────────────────────────
SESSION_CACHE_DIR = '.session_cache'
COOKIE_MAX_AGE = 24 * 60 * 60  # 24 hours in seconds


def _ensure_cache_dir():
    os.makedirs(SESSION_CACHE_DIR, exist_ok=True)


def _cache_path(email):
    h = hashlib.md5(email.encode()).hexdigest()
    return os.path.join(SESSION_CACHE_DIR, f"{h}.json")


def _save_cookies(email, cookies):
    """Persist session cookies to disk."""
    _ensure_cache_dir()
    data = {
        'email': email,
        'cookies': cookies,
        'saved_at': time.time(),
    }
    with open(_cache_path(email), 'w') as f:
        json.dump(data, f)


def _load_cookies(email):
    """Load cached cookies if they exist and are not expired."""
    path = _cache_path(email)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        if time.time() - data.get('saved_at', 0) > COOKIE_MAX_AGE:
            return None
        return data.get('cookies')
    except Exception:
        return None


def _build_headers(session):
    """Build LinkedIn API request headers from a session's cookies."""
    return {
        'Authority': 'www.linkedin.com',
        'Method': 'GET',
        'Scheme': 'https',
        'Accept': 'application/vnd.linkedin.normalized+json+2.1',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cookie': "; ".join([f"{key}={value}" for key, value in session.cookies.items()]),
        'Csrf-Token': session.cookies.get('JSESSIONID', '').strip('"'),
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
        'X-Li-Track': '{"clientVersion":"1.13.5589","mpVersion":"1.13.5589","osName":"web","timezoneOffset":-7,"timezone":"America/Los_Angeles","deviceFormFactor":"DESKTOP","mpName":"voyager-web","displayDensity":1,"displayWidth":360,"displayHeight":800}'
    }


def create_session(email, password):
    """
    Create an authenticated requests.Session for LinkedIn.

    First checks the cookie cache.  If cached cookies are valid, skips
    Selenium entirely.  Otherwise launches a browser for interactive login.
    """
    # Try cookie cache first
    cached = _load_cookies(email)
    if cached:
        session = requests.Session()
        for cookie in cached:
            session.cookies.set(cookie['name'], cookie['value'])
        # Quick validation — try a lightweight request
        try:
            headers = _build_headers(session)
            resp = session.get(
                'https://www.linkedin.com/voyager/api/me',
                headers=headers,
                timeout=10,
                allow_redirects=False,
            )
            if resp.status_code == 200:
                print(f'[+] Loaded cached session for "{email}"')
                return session
        except Exception:
            pass
        print(f'[!] Cached cookies expired for "{email}", launching browser...')

    # Selenium login
    if BROWSER == 'chrome':
        driver = webdriver.Chrome()
    elif BROWSER == 'edge':
        driver = webdriver.Edge()
    else:
        driver = webdriver.Chrome()

    driver.get('https://www.linkedin.com/checkpoint/rm/sign-in-another-account')

    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'username'))
    ).send_keys(email)

    driver.find_element(By.ID, 'password').send_keys(password)

    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]'))
        ).click()
    except Exception:
        try:
            driver.find_element(By.XPATH, '//*[@id="organic-div"]/form/div[3]/button').click()
        except Exception:
            driver.find_element(By.CSS_SELECTOR, '.btn__primary--large').click()

    time.sleep(1)
    input('Press ENTER after a successful login for "{}": '.format(email))
    driver.get('https://www.linkedin.com/jobs/search/?')
    time.sleep(1)
    cookies = driver.get_cookies()
    driver.quit()

    # Save cookies to cache
    _save_cookies(email, cookies)

    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])
    return session


def get_logins():
    """
    Read LinkedIn credentials from logins.csv.

    The CSV should have columns: emails, passwords
    (no 'method' column — single account supports both search and details).
    """
    logins = pd.read_csv('logins.csv')
    emails = logins['emails'].tolist()
    passwords = logins['passwords'].tolist()
    return emails, passwords


# ════════════════════════════════════════════════════════════════════════
# Shared Session Pool
# ════════════════════════════════════════════════════════════════════════

class SessionPool:
    """
    Singleton session manager.  Creates sessions once and shares them
    between JobSearchRetriever and JobDetailRetriever.
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    def __init__(self):
        emails, passwords = get_logins()
        self.sessions = []
        self.headers_list = []
        self._session_index = 0
        for email, password in zip(emails, passwords):
            session = create_session(email, password)
            headers = _build_headers(session)
            self.sessions.append(session)
            self.headers_list.append(headers)

    def get_next(self):
        """Return (session, headers) using round-robin."""
        s = self.sessions[self._session_index]
        h = self.headers_list[self._session_index]
        self._session_index = (self._session_index + 1) % len(self.sessions)
        return s, h

    @property
    def count(self):
        return len(self.sessions)


# ════════════════════════════════════════════════════════════════════════
# LinkedIn Search URL Builder
# ════════════════════════════════════════════════════════════════════════

# Maps config values to LinkedIn's Voyager API filter parameters
_EXPERIENCE_MAP = {
    'internship': '1', 'entry': '2', 'associate': '3',
    'mid-senior': '4', 'director': '5', 'executive': '6',
}

_JOB_TYPE_MAP = {
    'full-time': 'F', 'part-time': 'P', 'contract': 'C',
    'internship': 'I', 'temporary': 'T', 'volunteer': 'V',
}

_REMOTE_MAP = {
    'on-site': '1', 'remote': '2', 'hybrid': '3',
}

_DATE_POSTED_MAP = {
    'past_24h': 'r86400',
    'past_week': 'r604800',
    'past_month': 'r2592000',
}


def build_search_url(config: dict, start: int = 0) -> str:
    """
    Build a LinkedIn Voyager API search URL from a config dict.

    The URL targets the voyagerJobsDashJobCards endpoint with dynamic
    filters derived from the scrape config.
    """
    base = (
        'https://www.linkedin.com/voyager/api/voyagerJobsDashJobCards'
        '?decorationId=com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-187'
        '&count=25'
        '&q=jobSearch'
    )

    # Build the selectedFilters portion of the query
    filters = ['sortBy:List(DD)']

    # Keywords
    keywords = config.get('keywords', [])
    keyword_str = ' '.join(keywords) if isinstance(keywords, list) else str(keywords)

    # Experience levels
    exp_levels = config.get('experience_level', [])
    if exp_levels and isinstance(exp_levels, list):
        codes = [_EXPERIENCE_MAP.get(e.lower(), '') for e in exp_levels]
        codes = [c for c in codes if c]
        if codes:
            filters.append(f"experience:List({','.join(codes)})")

    # Job type
    job_types = config.get('job_type', [])
    if job_types and isinstance(job_types, list):
        codes = [_JOB_TYPE_MAP.get(t.lower(), '') for t in job_types]
        codes = [c for c in codes if c]
        if codes:
            filters.append(f"jobType:List({','.join(codes)})")

    # Remote filter
    remote = config.get('remote_filter', 'any')
    if remote and remote != 'any':
        code = _REMOTE_MAP.get(remote.lower(), '')
        if code:
            filters.append(f"workplaceType:List({code})")

    # Date posted
    date_posted = config.get('date_posted', 'any')
    if date_posted and date_posted != 'any':
        tpr = _DATE_POSTED_MAP.get(date_posted, '')
        if tpr:
            filters.append(f"timePostedRange:List({tpr})")

    filter_str = ','.join(filters)

    # Build location portion
    location = config.get('location', '')
    if location:
        # Append location to keywords since string geoIds are invalid in Voyager
        if keyword_str:
            keyword_str += f" {location}"
        else:
            keyword_str = str(location)

    # Combine query
    query = (
        f'(origin:JOB_SEARCH_PAGE_OTHER_ENTRY'
        f',selectedFilters:({filter_str})'
        f',spellCorrectionEnabled:true)'
    )

    from urllib.parse import quote
    url = f"{base}&query={quote(query)}&start={start}"
    if keyword_str:
        url += f"&keywords={quote(keyword_str)}"
    return url


# ════════════════════════════════════════════════════════════════════════
# Job Search Retriever
# ════════════════════════════════════════════════════════════════════════

class JobSearchRetriever:
    """
    Discovers new job postings via LinkedIn Voyager search API.

    Can be initialised with an explicit config dict (for dashboard-triggered
    scrapes) or without one (loads active config from DB).
    """
    def __init__(self, config=None):
        self.config = config
        pool = SessionPool.get_instance()
        self.pool = pool

        # Build default URL for backward-compat (no config → static URL)
        if self.config:
            self.job_search_link = build_search_url(self.config, start=0)
        else:
            search_query = '(origin:JOB_SEARCH_PAGE_OTHER_ENTRY,selectedFilters:(sortBy:List(DD)),spellCorrectionEnabled:true)'
            self.job_search_link = (
                f'https://www.linkedin.com/voyager/api/voyagerJobsDashJobCards'
                f'?decorationId=com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollection-187'
                f'&count=25&q=jobSearch&query={search_query}&start=0'
            )

    def get_jobs(self, start=0):
        """
        Fetch a page of job search results.

        Returns dict of {job_id: {'title': ..., 'sponsored': bool}}
        """
        if self.config:
            url = build_search_url(self.config, start=start)
        else:
            url = self.job_search_link

        session, headers = self.pool.get_next()
        results = session.get(url, headers=headers, allow_redirects=False, timeout=15)

        if results.status_code != 200:
            msg = 'Status code {} for search\nURL: {}\nText: {}'.format(
                results.status_code, results.url, results.text
            )
            if results.status_code in (302, 303):
                msg = f"Session expired or auth blocked (Redirect {results.status_code}). Please delete linkedin_cookies_*.json and restart to re-login."
            raise Exception(msg)

        results = results.json()
        job_ids = {}

        for r in results.get('included', []):
            if r.get('$type') == 'com.linkedin.voyager.dash.jobs.JobPostingCard' and 'referenceId' in r:
                title = r.get('jobPostingTitle')
                if not title:
                    continue
                job_id = int(strip_val(r['jobPostingUrn'], 1))
                job_ids[job_id] = {'sponsored': False, 'title': title}
                for x in r.get('footerItems', []):
                    if x.get('type') == 'PROMOTED':
                        job_ids[job_id]['sponsored'] = True
                        break

        return job_ids


# ════════════════════════════════════════════════════════════════════════
# Job Detail Retriever
# ════════════════════════════════════════════════════════════════════════

class JobDetailRetriever:
    """
    Retrieves full job details for individual job postings.

    Shares the same SessionPool as JobSearchRetriever.
    """
    def __init__(self):
        self.error_count = 0
        self.job_details_link = (
            "https://www.linkedin.com/voyager/api/jobs/jobPostings/{}"
            "?decorationId=com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65"
        )
        self.pool = SessionPool.get_instance()
        self.variable_paths = pd.read_csv('json_paths/data_variables.csv')

    def get_job_details(self, job_ids):
        job_details = {}
        for job_id in job_ids:
            error = False
            session, headers = self.pool.get_next()
            try:
                details = session.get(
                    self.job_details_link.format(job_id),
                    headers=headers,
                    timeout=15,
                    allow_redirects=False,
                )
            except requests.exceptions.Timeout:
                print('Timeout for job {}'.format(job_id))
                error = True
                details = None
            except requests.exceptions.RequestException as e:
                print('Request error for job {}: {}'.format(job_id, e))
                error = True
                details = None

            if details is not None and details.status_code != 200:
                if details.status_code in (302, 303):
                    job_details[job_id] = {'error': "Session expired / Auth blocked. Delete cookies and restart."}
                else:
                    job_details[job_id] = -1
                    print('Status code {} for job {}\nText: {}'.format(
                        details.status_code, job_id, details.text
                    ))
                error = True

            if error:
                self.error_count += 1
                if self.error_count > 10:
                    raise Exception('Too many errors')
            else:
                self.error_count = 0
                job_details[job_id] = details.json()
                print('Job {} done'.format(job_id))

            time.sleep(.3)
        return job_details
