import http.server
import json
import sqlite3
import urllib.parse
import os

PORT = 8000
DB_FILE = 'linkedin_jobs.db'

class JobServerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard logging output to keep the console clean,
        # but feel free to print custom logs if needed.
        pass

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Simple routing
        if path == '/' or path == '/index.html':
            self.serve_file('index.html', 'text/html')
        elif path == '/api/jobs':
            print("[GET] /api/jobs requested")
            self.handle_get_jobs()
        elif path.startswith('/api/job/'):
            job_id_str = path.split('/')[-1]
            print(f"[GET] /api/job/{job_id_str} requested")
            try:
                job_id = int(job_id_str)
                self.handle_get_job_detail(job_id)
            except ValueError:
                self.send_error_response(400, "Invalid Job ID format")
        else:
            # Fallback to serving static files relative to root
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
                self.serve_file(file_path, content_type)
            else:
                self.send_error_response(404, "Page or File Not Found")
                
    def serve_file(self, filename, content_type):
        try:
            if not os.path.exists(filename):
                self.send_error_response(404, f"File {filename} not found")
                return
            with open(filename, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_response(500, f"Error reading file: {str(e)}")

    def send_error_response(self, status_code, message):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        err_json = json.dumps({"error": message})
        self.wfile.write(err_json.encode('utf-8'))
            
    def handle_get_jobs(self):
        if not os.path.exists(DB_FILE):
            self.send_error_response(404, "SQLite database 'linkedin_jobs.db' not found. Run the scraper first.")
            return

        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if jobs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
            if not cursor.fetchone():
                conn.close()
                self.send_error_response(400, "Database exists, but 'jobs' table is not created yet. Run the scraper first.")
                return

            # Query list data (excluding large columns like description and skills_desc)
            query = """
                SELECT 
                    j.job_id, 
                    j.title, 
                    c.name as company_name, 
                    j.location, 
                    j.formatted_work_type, 
                    j.formatted_experience_level, 
                    s.min_salary, 
                    s.max_salary, 
                    s.pay_period, 
                    s.currency,
                    j.views, 
                    j.applies, 
                    j.sponsored,
                    j.scraped,
                    j.job_posting_url
                FROM jobs j
                LEFT JOIN companies c ON j.company_id = c.company_id
                LEFT JOIN salaries s ON j.job_id = s.job_id
                WHERE j.scraped != -2
                ORDER BY j.job_id DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            jobs = [dict(row) for row in rows]
            conn.close()
            
            # Respond with JSON
            response_data = json.dumps(jobs).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', len(response_data))
            self.end_headers()
            self.wfile.write(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Database query error: {str(e)}")
            
    def handle_get_job_detail(self, job_id):
        if not os.path.exists(DB_FILE):
            self.send_error_response(404, "Database file not found.")
            return

        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Query full details including description and company details
            query = """
                SELECT 
                    j.job_id, 
                    j.title, 
                    j.description,
                    j.skills_desc,
                    c.name as company_name, 
                    c.description as company_description,
                    c.url as company_url,
                    j.location, 
                    j.formatted_work_type, 
                    j.formatted_experience_level, 
                    s.min_salary, 
                    s.max_salary, 
                    s.pay_period, 
                    s.currency,
                    j.views, 
                    j.applies, 
                    j.sponsored,
                    j.scraped,
                    j.job_posting_url,
                    j.application_url
                FROM jobs j
                LEFT JOIN companies c ON j.company_id = c.company_id
                LEFT JOIN salaries s ON j.job_id = s.job_id
                WHERE j.job_id = ?
            """
            cursor.execute(query, (job_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row is None:
                self.send_error_response(404, f"Job with ID {job_id} not found.")
                return
                
            job_detail = dict(row)
            response_data = json.dumps(job_detail).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', len(response_data))
            self.end_headers()
            self.wfile.write(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Database query error: {str(e)}")

def run_server():
    server_address = ('', PORT)
    httpd = http.server.HTTPServer(server_address, JobServerHandler)
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
