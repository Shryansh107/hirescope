import os
import json
import requests
from scripts.supabase_client import get_supabase_client

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Tool Definitions
TOOLS = [
    {
        "function_declarations": [
            {
                "name": "get_job_stats",
                "description": "Get general statistics about all jobs currently scraped and stored in the database.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {}
                }
            },
            {
                "name": "search_jobs",
                "description": "Search and filter jobs in the database by title, company, location, required skills, or minimum salary.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Filter by job title (e.g., 'Software Engineer', 'React')"},
                        "company": {"type": "STRING", "description": "Filter by company name"},
                        "location": {"type": "STRING", "description": "Filter by location (e.g., 'India', 'Remote')"},
                        "skills": {"type": "STRING", "description": "Filter by required skills or technologies"},
                        "min_salary": {"type": "NUMBER", "description": "Filter jobs with a maximum salary or minimum salary greater than this value"},
                        "limit": {"type": "INTEGER", "description": "Maximum number of results to return (default 10)"}
                    }
                }
            },
            {
                "name": "get_job_detail",
                "description": "Get the detailed information of a specific job by its job_id, including its full description, skills description, application URL, and company details.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "job_id": {"type": "INTEGER", "description": "The unique ID of the job to retrieve details for."}
                    },
                    "required": ["job_id"]
                }
            }
        ]
    }
]

def get_job_stats():
    """Fetches and computes statistics on the scraped jobs."""
    try:
        client = get_supabase_client()
        jobs = client.select_job_dashboard() or []
        if not jobs:
            return {"status": "success", "message": "No jobs found in the database."}

        total_jobs = len(jobs)
        scraped_jobs = sum(1 for j in jobs if j.get("scraped") == 1)
        pending_jobs = sum(1 for j in jobs if j.get("scraped") == 0)
        remote_jobs = sum(1 for j in jobs if j.get("formatted_work_type") and "remote" in j["formatted_work_type"].lower())
        
        # Calculate salary statistics (in USD/INR, for simplicity we average what we find)
        salaries = [j.get("max_salary") for j in jobs if j.get("max_salary") is not None]
        avg_max_salary = sum(salaries) / len(salaries) if salaries else None

        # Top companies
        companies = {}
        for j in jobs:
            c = j.get("company_name")
            if c:
                companies[c] = companies.get(c, 0) + 1
        top_companies = sorted(companies.items(), key=lambda x: x[1], reverse=True)[:5]

        # Top locations
        locations = {}
        for j in jobs:
            loc = j.get("location")
            if loc:
                locations[loc] = locations.get(loc, 0) + 1
        top_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "status": "success",
            "total_jobs": total_jobs,
            "scraped_jobs": scraped_jobs,
            "pending_jobs": pending_jobs,
            "remote_jobs": remote_jobs,
            "average_max_salary": avg_max_salary,
            "top_companies": dict(top_companies),
            "top_locations": dict(top_locations)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def search_jobs(title=None, company=None, location=None, skills=None, min_salary=None, limit=10):
    """Searches jobs based on filters in Python for maximum compatibility and flexibility."""
    try:
        client = get_supabase_client()
        jobs = client.select_job_dashboard() or []
        
        filtered = []
        for j in jobs:
            # Title filter
            if title and title.lower() not in (j.get("title") or "").lower():
                continue
            # Company filter
            if company and company.lower() not in (j.get("company_name") or "").lower():
                continue
            # Location filter
            if location and location.lower() not in (j.get("location") or "").lower():
                # Check remote filter if they explicitly asked for Remote
                if location.lower() == "remote":
                    if not j.get("formatted_work_type") or "remote" not in j["formatted_work_type"].lower():
                        continue
                else:
                    continue
            # Salary filter
            if min_salary:
                max_sal = j.get("max_salary")
                min_sal = j.get("min_salary")
                if max_sal is None and min_sal is None:
                    continue
                val = max_sal if max_sal is not None else min_sal
                if val < min_salary:
                    continue
            # Skills filter (matched keywords or in title/location/etc)
            if skills:
                matched_kws = j.get("matched_keywords") or []
                skills_match = False
                for kw in matched_kws:
                    if skills.lower() in kw.lower():
                        skills_match = True
                        break
                if not skills_match and skills.lower() not in (j.get("title") or "").lower():
                    continue
            
            # Format output fields slightly to save context tokens
            filtered.append({
                "job_id": j.get("job_id"),
                "title": j.get("title"),
                "company_name": j.get("company_name"),
                "location": j.get("location"),
                "formatted_work_type": j.get("formatted_work_type"),
                "formatted_experience_level": j.get("formatted_experience_level"),
                "min_salary": j.get("min_salary"),
                "max_salary": j.get("max_salary"),
                "pay_period": j.get("pay_period"),
                "currency": j.get("currency"),
                "relevance_score": j.get("relevance_score"),
                "scraped": j.get("scraped")
            })

        # Sort by relevance score desc
        filtered = sorted(filtered, key=lambda x: x.get("relevance_score") or 0, reverse=True)
        return {"status": "success", "jobs": filtered[:limit], "total_matches": len(filtered)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def get_job_detail(job_id):
    """Fetches details for a specific job_id."""
    try:
        client = get_supabase_client()
        detail = client.select_job_detail(job_id)
        if not detail:
            return {"status": "error", "message": f"Job with ID {job_id} not found."}
        
        # Selectively return details to avoid overloading the model
        return {
            "status": "success",
            "job_id": detail.get("job_id"),
            "title": detail.get("title"),
            "company_name": detail.get("company_name"),
            "company_description": detail.get("company_description")[:500] if detail.get("company_description") else None,
            "location": detail.get("location"),
            "formatted_work_type": detail.get("formatted_work_type"),
            "formatted_experience_level": detail.get("formatted_experience_level"),
            "description": detail.get("description"),
            "skills_desc": detail.get("skills_desc"),
            "views": detail.get("views"),
            "applies": detail.get("applies"),
            "job_posting_url": detail.get("job_posting_url"),
            "application_url": detail.get("application_url"),
            "relevance_score": detail.get("relevance_score"),
            "matched_keywords": detail.get("matched_keywords")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def execute_tool(call):
    name = call["name"]
    args = call.get("args", {})
    
    if name == "get_job_stats":
        return get_job_stats()
    elif name == "search_jobs":
        return search_jobs(**args)
    elif name == "get_job_detail":
        return get_job_detail(**args)
    else:
        return {"status": "error", "message": f"Unknown tool: {name}"}

def run_chat_session(messages):
    """
    Executes a chat request against Gemini API.
    Supports tool invocation loop.
    messages is a list of {"role": "user"|"model"|"function", "content": text, "name": function_name, "response": function_response}
    """
    if not GEMINI_API_KEY:
        return {"error": "Missing GEMINI_API_KEY. Please configure it in your .env file."}

    # Format the history into Gemini's payload format
    contents = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": msg["content"]}]})
        elif role == "model":
            parts = []
            if msg.get("content"):
                parts.append({"text": msg["content"]})
            if msg.get("function_calls"):
                for fc in msg["function_calls"]:
                    parts.append({"functionCall": fc})
            contents.append({"role": "model", "parts": parts})
        elif role == "function":
            contents.append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": msg["name"],
                        "response": msg["response"]
                    }
                }]
            })

    system_instruction = (
        "You are the BMW M-inspired high-performance Job Scraper AI assistant. "
        "You have direct access to the scraped jobs database. Answer questions concisely, professionally, and "
        "directly using the tools provided. When answering, cite jobs with their title, company, and location. "
        "Do not make up job information; only use facts returned by the tools."
    )

    payload = {
        "contents": contents,
        "tools": TOOLS,
        "systemInstruction": {"parts": [{"text": system_instruction}]}
    }

    try:
        response = requests.post(
            f"{GEMINI_ENDPOINT}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        if response.status_code != 200:
            return {"error": f"Gemini API returned error code {response.status_code}: {response.text}"}
        
        res_data = response.json()
        candidates = res_data.get("candidates", [])
        if not candidates:
            return {"content": "I couldn't process that request."}
        
        content_part = candidates[0].get("content", {})
        parts = content_part.get("parts", [])
        
        text_response = ""
        function_calls = []
        
        for part in parts:
            if "text" in part:
                text_response += part["text"]
            if "functionCall" in part:
                function_calls.append(part["functionCall"])

        result = {
            "role": "model",
            "content": text_response
        }
        if function_calls:
            result["function_calls"] = function_calls

        return result

    except Exception as e:
        return {"error": f"Error communicating with Gemini: {str(e)}"}
