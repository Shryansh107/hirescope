import os
import re
import threading
import time
import json
import asyncio
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.scripts.create_db import create_tables
from db.scripts.config_db import (
    save_config, get_config, list_configs, delete_config,
    activate_config, get_active_config,
    create_run, update_run_progress, get_run, get_current_run, list_runs,
    cleanup_stale_runs,
)
from BE.scripts.supabase_client import using_supabase

PORT = 8000

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
    """Verify connection to Supabase on startup."""
    if os.getenv("TESTING") == "true":
        return
    try:
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        client.select_configs()
        print("[+] Successfully connected to Supabase database.")
    except Exception as e:
        print(f"[!] Critical Error: Failed to connect to Supabase: {e}")
        import sys
        sys.exit(1)


def _reset_default_config():
    """Reset active config to Default Tech and restore its permanent values on Supabase."""
    if os.getenv("TESTING") == "true":
        try:
            import sqlite3
            from scripts.config_db import DB_FILE
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scrape_configs WHERE profile_name = 'Quick Scrape'")
            conn.commit()
            cursor.execute("SELECT id FROM scrape_configs WHERE profile_name = ?", (DEFAULT_TECH_CONFIG['profile_name'],))
            row = cursor.fetchone()
            conn.close()

            from scripts.config_db import save_config, activate_config
            if row:
                default_id = row[0]
                cfg = dict(DEFAULT_TECH_CONFIG)
                cfg['id'] = default_id
                save_config(cfg)
                activate_config(default_id)
            else:
                cfg_id = save_config(dict(DEFAULT_TECH_CONFIG))
                activate_config(cfg_id)
        except Exception:
            pass
        return

    try:
        from scripts.supabase_client import get_supabase_client
        client = get_supabase_client()

        # 1. Delete temporary Quick Scrape profiles
        client._request("DELETE", "scrape_configs", params={"profile_name": "eq.Quick Scrape"})

        # 2. Check if default config already exists
        configs = client.select_configs()
        default_profile = next((c for c in configs if c['profile_name'] == DEFAULT_TECH_CONFIG['profile_name']), None)

        if default_profile:
            default_id = default_profile['id']
            cfg = dict(DEFAULT_TECH_CONFIG)
            cfg['id'] = default_id
            client.update_config(default_id, cfg)
            client.activate_config(default_id)
        else:
            cfg_id = client.insert_config(dict(DEFAULT_TECH_CONFIG))
            client.activate_config(cfg_id)
        print("[+] Configurations reset to Default Tech config on Supabase.")
    except Exception as e:
        print(f"[!] Warning: Failed to reset config on Supabase: {e}")


_ensure_db()


app = FastAPI(title="LinkedIn Job Scraper API")

# Setup CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/index.html")
async def serve_root():
    _reset_default_config()
    index_path = os.path.join('FE', 'dist', 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="FE/dist/index.html not found. Please build frontend first.")


# ── Jobs API ───────────────────────────────────────────────────

@app.get("/api/jobs")
async def get_jobs():
    try:
        from BE.scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        jobs = client.select_job_dashboard()
        return jobs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/api/job/{job_id}")
async def get_job_detail(job_id: int):
    try:
        from BE.scripts.supabase_client import get_supabase_client
        client = get_supabase_client()
        job = client.select_job_detail(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ── Config API ─────────────────────────────────────────────────

@app.get("/api/config/list")
async def get_config_list():
    try:
        return list_configs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/{config_id}")
async def get_config_by_id(config_id: int):
    try:
        cfg = get_config(config_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Config not found")
        return cfg
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/save")
async def save_scrape_config(request: Request):
    try:
        data = await request.json()
        if not data.get('profile_name'):
            raise HTTPException(status_code=400, detail="profile_name is required")
        config_id = save_config(data)
        return {"id": config_id, "message": "saved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/config/{config_id}")
async def delete_scrape_config(config_id: int):
    try:
        delete_config(config_id)
        return {"message": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/{config_id}/activate")
async def activate_scrape_config(config_id: int):
    try:
        cfg = get_config(config_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail="Config not found")
        activate_config(config_id)
        return {"message": "activated", "id": config_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Scrape API ─────────────────────────────────────────────────

@app.post("/api/scrape/start")
async def start_scrape():
    global _scraper_thread

    with _scraper_lock:
        # Check if already running
        current = get_current_run()
        if current and current.get('status') == 'running':
            raise HTTPException(status_code=409, detail="A scrape is already running")

        # Validate active config
        config = get_active_config()
        if not config:
            raise HTTPException(status_code=400, detail="No active scrape config. Save and activate a config first.")

        keywords = config.get('keywords', [])
        job_titles = config.get('job_titles', [])
        if not keywords and not job_titles:
            raise HTTPException(status_code=400, detail="Config must have at least keywords or job_titles set")

        # Create run record
        run_id = create_run(config['id'])

        # Start scraper in background thread
        from BE.scripts.scrape_runner import run_scrape
        _scraper_thread = threading.Thread(
            target=run_scrape, args=(run_id,), daemon=True
        )
        _scraper_thread.start()

        return {"run_id": run_id, "message": "Scraping started"}


@app.get("/api/scrape/status")
async def get_scrape_status(request: Request):
    """Return current run status as JSON or SSE stream."""
    accept = request.headers.get('Accept', '')

    if 'text/event-stream' in accept:
        async def sse_generator():
            try:
                while True:
                    # Check if client disconnected
                    if await request.is_disconnected():
                        break

                    run = get_current_run()
                    if run is None:
                        # Check most recent completed run
                        runs = list_runs(limit=1)
                        run = runs[0] if runs else None

                    if run:
                        data = json.dumps(run)
                        yield f"data: {data}\n\n"
                        # Stop streaming if the run is finished
                        if run.get('status') in ('completed', 'stopped', 'failed'):
                            break
                    else:
                        yield f"data: {json.dumps({'status': 'idle'})}\n\n"
                        break

                    await asyncio.sleep(2)
            except asyncio.CancelledError:
                pass

        return StreamingResponse(sse_generator(), media_type="text/event-stream")
    else:
        # Regular JSON mode
        run = get_current_run()
        if run is None:
            runs = list_runs(limit=1)
            run = runs[0] if runs else {"status": "idle"}
        return run


@app.post("/api/scrape/stop")
async def stop_scrape():
    current = get_current_run()
    if not current or current.get('status') != 'running':
        raise HTTPException(status_code=400, detail="No active scrape to stop")
    update_run_progress(current['run_id'], status='stopping')
    return {"message": "Stop signal sent", "run_id": current['run_id']}


@app.get("/api/scrape/history")
async def get_scrape_history():
    try:
        runs = list_runs(limit=50)
        return runs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        messages = data.get('messages', [])
        
        from BE.scripts.chatbot import run_chat_session, execute_tool
        
        # Simple agent loop to handle tool execution automatically
        # Limit the loops to 5 to avoid infinite execution
        loop_limit = 5
        result = None
        for _ in range(loop_limit):
            result = run_chat_session(messages)
            if "error" in result:
                return result
            
            # Check if we need to call tools
            if "function_calls" in result:
                # Append model message to history
                messages.append(result)
                
                # Execute all function calls
                for call in result["function_calls"]:
                    tool_result = execute_tool(call)
                    messages.append({
                        "role": "function",
                        "name": call["name"],
                        "response": tool_result
                    })
                # Loop back to let model analyze tool outputs
                continue
            else:
                # No more function calls, send final response
                return result
        
        # If loop limit reached, send whatever result we have
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


# ── Static file fallback ───────────────────────────────────────

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    # Try serving from FE/dist
    dist_path = os.path.join('FE', 'dist', file_path)
    if os.path.isfile(dist_path):
        return FileResponse(dist_path)
    # Try serving from root directory
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Not Found")


def run_server():
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
    
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == '__main__':
    run_server()
