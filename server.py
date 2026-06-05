import http.server
import json
import sqlite3
import urllib.parse
import os
import re
import threading
import time

from scripts.create_db import create_tables
from scripts.config_db import (
    save_config, get_config, list_configs, delete_config,
    activate_config, get_active_config,
    create_run, update_run_progress, get_run, get_current_run, list_runs,
    cleanup_stale_runs,
)

PORT = 8000
DB_FILE = 'linkedin_jobs.db'

# Global reference to the active scraper thread
_scraper_thread = None
_scraper_lock = threading.Lock()


DEFAULT_TECH_CONFIG = {
    'profile_name': 'Default Tech (0-2 years)',
    'keywords': [
        'software engineer', 'software developer', 'frontend developer', 
        'backend developer', 'fullstack developer', 'python developer', 
        'golang developer', 'react developer', 'node developer'
    ],
    'job_titles': [
        'Software Engineer', 'Software Developer', 'Associate Software Engineer',
        'Junior Software Engineer', 'Graduate Software Engineer', 'Frontend Engineer',
        'Backend Engineer', 'Fullstack Engineer', 'Full Stack Developer', 'DevOps Engineer',
        'Cloud Engineer', 'SRE', 'Site Reliability Engineer', 'Data Engineer',
        'QA Engineer', 'Automation Engineer', 'SDET', 'Mobile Developer',
        'iOS Developer', 'Android Developer', 'React Native Developer'
    ],
    'excluded_keywords': [
        'senior', 'sr.', 'sr ', 'lead', 'principal', 'architect', 'staff', 'head',
        'director', 'vp', 'manager', 'product manager', 'project manager',
        'program manager', 'scrum master', 'agile coach', 'business analyst',
        'data analyst', 'designer', 'ui/ux', 'technical writer', 'sales',
        'marketing', 'recruiter', 'human resources', 'hr', 'operations', 'customer success'
    ],
    'location': '[{"location": "India", "workplace": ["any"]}]',
    'remote_filter': 'any',
    'job_type': ['full-time', 'contract', 'internship'],
    'experience_level': ['internship', 'entry', 'associate'],
    'years_of_experience_min': 0,
    'years_of_experience_max': 2,
    'expected_pay_min': None,
    'expected_pay_max': None,
    'pay_currency': 'USD',
    'required_skills': [
        'go', 'golang', 'c++', 'react', 'react.js', 'javascript', 'typescript', 
        'python', 'java', 'c#', 'rust', 'html', 'css', 'sql', 'git', 'docker', 
        'aws', 'kubernetes'
    ],
    'preferred_skills': [],
    'programming_languages': [],
    'company_names': [],
    'excluded_companies': [],
    'company_size': [],
    'industry': [],
    'date_posted': 'past_week',
    'max_jobs_to_scrape': 500,
    'pages_to_scrape': 100,
    'weight_title_match': 8,
    'weight_skills_match': 6,
    'weight_salary_match': 4,
    'is_active': 1,
}


def _ensure_db():
    """Make sure the DB and all tables exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    create_tables(conn, cursor)
    conn.close()

    # Seed default tech configuration if no configs exist
    try:
        if not list_configs():
            print("[+] Database is empty. Seeding default tech configuration profile...")
            cfg_id = save_config(dict(DEFAULT_TECH_CONFIG))
            activate_config(cfg_id)
            print(f"[+] Default profile seeded and activated (ID: {cfg_id})")
    except Exception as e:
        print(f"[!] Warning: Failed to seed default configuration: {e}")


def _reset_default_config():
    """Clear all profiles in database and restore default tech config."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scrape_configs;")
        conn.commit()
        conn.close()

        cfg_id = save_config(dict(DEFAULT_TECH_CONFIG))
        activate_config(cfg_id)
        print("[+] Configurations reset to Default Tech config.")
    except Exception as e:
        print(f"[!] Warning: Failed to reset config: {e}")


_ensure_db()


class JobServerHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    # ── Routing helpers ────────────────────────────────────────────────

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status, message):
        self._send_json({"error": message}, status)

    def _match(self, pattern):
        """Match self.path (without query string) against a regex pattern."""
        path = urllib.parse.urlparse(self.path).path
        return re.match(pattern, path)

    # ── CORS preflight ─────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
        self.end_headers()

    # ── GET routes ─────────────────────────────────────────────────────

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path

        # Static files
        if path == '/' or path == '/index.html':
            _reset_default_config()
            self._serve_file('index.html', 'text/html')

        # ── Jobs API ───────────────────────────────────────────────────
        elif path == '/api/jobs':
            self._handle_get_jobs()

        elif self._match(r'^/api/job/(\d+)$'):
            job_id = int(self._match(r'^/api/job/(\d+)$').group(1))
            self._handle_get_job_detail(job_id)

        # ── Config API ─────────────────────────────────────────────────
        elif path == '/api/config/list':
            self._handle_config_list()

        elif self._match(r'^/api/config/(\d+)$'):
            config_id = int(self._match(r'^/api/config/(\d+)$').group(1))
            self._handle_config_get(config_id)

        # ── Scrape API ─────────────────────────────────────────────────
        elif path == '/api/scrape/status':
            self._handle_scrape_status()

        elif path == '/api/scrape/history':
            self._handle_scrape_history()

        # ── Static file fallback ───────────────────────────────────────
        else:
            file_path = path.lstrip('/')
            if file_path and os.path.exists(file_path) and os.path.isfile(file_path):
                content_type = 'text/plain'
                if file_path.endswith('.html'):
                    content_type = 'text/html'
                elif file_path.endswith('.css'):
                    content_type = 'text/css'
                elif file_path.endswith('.js'):
                    content_type = 'application/javascript'
                elif file_path.endswith('.json'):
                    content_type = 'application/json'
                self._serve_file(file_path, content_type)
            else:
                self._send_error(404, "Not Found")

    # ── POST routes ────────────────────────────────────────────────────

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == '/api/config/save':
            self._handle_config_save()

        elif self._match(r'^/api/config/(\d+)/activate$'):
            config_id = int(self._match(r'^/api/config/(\d+)/activate$').group(1))
            self._handle_config_activate(config_id)

        elif path == '/api/scrape/start':
            self._handle_scrape_start()

        elif path == '/api/scrape/stop':
            self._handle_scrape_stop()

        else:
            self._send_error(404, "Not Found")

    # ── DELETE routes ──────────────────────────────────────────────────

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path

        m = self._match(r'^/api/config/(\d+)$')
        if m:
            config_id = int(m.group(1))
            self._handle_config_delete(config_id)
        else:
            self._send_error(404, "Not Found")

    # ══════════════════════════════════════════════════════════════════
    # Handler implementations
    # ══════════════════════════════════════════════════════════════════

    # ── Static file serving ────────────────────────────────────────────

    def _serve_file(self, filename, content_type):
        try:
            if not os.path.exists(filename):
                self._send_error(404, f"File {filename} not found")
                return
            with open(filename, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_error(500, f"Error reading file: {str(e)}")

    # ── Jobs endpoints ─────────────────────────────────────────────────

    def _handle_get_jobs(self):
        if not os.path.exists(DB_FILE):
            self._send_error(404, "Database not found. Run the scraper first.")
            return
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
            if not cursor.fetchone():
                conn.close()
                self._send_error(400, "No jobs table. Run the scraper first.")
                return

            query = """
                SELECT
                    j.job_id, j.title,
                    c.name as company_name,
                    j.location, j.formatted_work_type,
                    j.formatted_experience_level, j.years_experience,
                    s.min_salary, s.max_salary, s.pay_period, s.currency,
                    j.views, j.applies, j.sponsored, j.scraped,
                    j.job_posting_url, j.relevance_score, j.matched_keywords,
                    j.posted_at, j.scraped_at, j.discovered_at
                FROM jobs j
                LEFT JOIN companies c ON j.company_id = c.company_id
                LEFT JOIN salaries s ON j.job_id = s.job_id
                WHERE j.scraped != -2
                GROUP BY j.job_id
                ORDER BY j.job_id DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            jobs = [dict(row) for row in rows]
            conn.close()
            self._send_json(jobs)
        except Exception as e:
            self._send_error(500, f"Database error: {str(e)}")

    def _handle_get_job_detail(self, job_id):
        if not os.path.exists(DB_FILE):
            self._send_error(404, "Database not found.")
            return
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT
                    j.job_id, j.title, j.description, j.skills_desc,
                    c.name as company_name,
                    c.description as company_description,
                    c.url as company_url,
                    j.location, j.formatted_work_type,
                    j.formatted_experience_level,
                    s.min_salary, s.max_salary, s.pay_period, s.currency,
                    j.views, j.applies, j.sponsored, j.scraped,
                    j.job_posting_url, j.application_url,
                    j.relevance_score, j.matched_keywords,
                    j.posted_at, j.scraped_at, j.discovered_at
                FROM jobs j
                LEFT JOIN companies c ON j.company_id = c.company_id
                LEFT JOIN salaries s ON j.job_id = s.job_id
                WHERE j.job_id = ?
            """
            cursor.execute(query, (job_id,))
            row = cursor.fetchone()
            conn.close()
            if row is None:
                self._send_error(404, f"Job {job_id} not found.")
                return
            self._send_json(dict(row))
        except Exception as e:
            self._send_error(500, f"Database error: {str(e)}")

    # ── Config endpoints ───────────────────────────────────────────────

    def _handle_config_list(self):
        try:
            configs = list_configs()
            self._send_json(configs)
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_config_get(self, config_id):
        try:
            cfg = get_config(config_id)
            if cfg is None:
                self._send_error(404, "Config not found")
            else:
                self._send_json(cfg)
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_config_save(self):
        try:
            data = self._read_body()
            if not data.get('profile_name'):
                self._send_error(400, "profile_name is required")
                return
            config_id = save_config(data)
            self._send_json({"id": config_id, "message": "saved"})
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_config_delete(self, config_id):
        try:
            delete_config(config_id)
            self._send_json({"message": "deleted"})
        except Exception as e:
            self._send_error(500, str(e))

    def _handle_config_activate(self, config_id):
        try:
            cfg = get_config(config_id)
            if cfg is None:
                self._send_error(404, "Config not found")
                return
            activate_config(config_id)
            self._send_json({"message": "activated", "id": config_id})
        except Exception as e:
            self._send_error(500, str(e))

    # ── Scrape endpoints ───────────────────────────────────────────────

    def _handle_scrape_start(self):
        global _scraper_thread

        with _scraper_lock:
            # Check if already running
            current = get_current_run()
            if current and current.get('status') == 'running':
                self._send_error(409, "A scrape is already running")
                return

            # Validate active config
            config = get_active_config()
            if not config:
                self._send_error(400, "No active scrape config. Save and activate a config first.")
                return

            keywords = config.get('keywords', [])
            job_titles = config.get('job_titles', [])
            if not keywords and not job_titles:
                self._send_error(400, "Config must have at least keywords or job_titles set")
                return

            # Create run record
            run_id = create_run(config['id'])

            # Start scraper in background thread
            from scripts.scrape_runner import run_scrape
            _scraper_thread = threading.Thread(
                target=run_scrape, args=(run_id,), daemon=True
            )
            _scraper_thread.start()

            self._send_json({"run_id": run_id, "message": "Scraping started"})

    def _handle_scrape_status(self):
        """Return current run status as JSON or SSE stream."""
        accept = self.headers.get('Accept', '')

        if 'text/event-stream' in accept:
            # SSE mode
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            try:
                while True:
                    run = get_current_run()
                    if run is None:
                        # Check most recent completed run
                        runs = list_runs(limit=1)
                        run = runs[0] if runs else None

                    if run:
                        data = json.dumps(run)
                        self.wfile.write(f"data: {data}\n\n".encode('utf-8'))
                        self.wfile.flush()

                        # Stop streaming if the run is finished
                        if run.get('status') in ('completed', 'stopped', 'failed'):
                            break
                    else:
                        self.wfile.write(f"data: {json.dumps({'status': 'idle'})}\n\n".encode('utf-8'))
                        self.wfile.flush()
                        break

                    time.sleep(2)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            # Regular JSON mode
            run = get_current_run()
            if run is None:
                runs = list_runs(limit=1)
                run = runs[0] if runs else {"status": "idle"}
            self._send_json(run)

    def _handle_scrape_stop(self):
        current = get_current_run()
        if not current or current.get('status') != 'running':
            self._send_error(400, "No active scrape to stop")
            return
        update_run_progress(current['run_id'], status='stopping')
        self._send_json({"message": "Stop signal sent", "run_id": current['run_id']})

    def _handle_scrape_history(self):
        try:
            runs = list_runs(limit=50)
            self._send_json(runs)
        except Exception as e:
            self._send_error(500, str(e))


def run_server():
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, JobServerHandler)
    # Reset any stale runs left from a previous crash/interruption
    try:
        cleanup_stale_runs()
    except Exception as e:
        print(f"[!] Warning: Failed to cleanup stale scrape runs: {e}")

    print(f"\n=======================================================")
    print(f"  LinkedIn Job Scraper Dashboard")
    print(f"  Running locally at: http://localhost:{PORT}/")
    print(f"  Close server by pressing: Ctrl+C")
    print(f"=======================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] Stopping server...")
        httpd.server_close()
        print("[+] Server stopped.")

if __name__ == '__main__':
    run_server()
