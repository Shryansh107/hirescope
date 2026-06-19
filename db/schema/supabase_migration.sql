-- Supabase Database Migration
-- Run this script in the Supabase SQL Editor (SQL Web Editor -> New query)
-- to update an existing older schema to the latest schema structure.

-- 1. Upgrade the jobs table with new columns if they do not exist
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS posted_at timestamptz;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS scraped_at timestamptz;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS discovered_at timestamptz DEFAULT now();
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS relevance_score integer;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS matched_keywords jsonb;
ALTER TABLE public.jobs ADD COLUMN IF NOT EXISTS scrape_run_id bigint;

-- 2. Create the scrape_configs table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.scrape_configs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  profile_name text NOT NULL,
  keywords jsonb DEFAULT '[]'::jsonb,
  job_titles jsonb DEFAULT '[]'::jsonb,
  excluded_keywords jsonb DEFAULT '[]'::jsonb,
  location text DEFAULT '',
  remote_filter text DEFAULT 'any',
  job_type jsonb DEFAULT '[]'::jsonb,
  experience_level jsonb DEFAULT '[]'::jsonb,
  years_of_experience_min integer,
  years_of_experience_max integer,
  expected_pay_min integer,
  expected_pay_max integer,
  pay_currency text DEFAULT 'USD',
  required_skills jsonb DEFAULT '[]'::jsonb,
  preferred_skills jsonb DEFAULT '[]'::jsonb,
  programming_languages jsonb DEFAULT '[]'::jsonb,
  company_names jsonb DEFAULT '[]'::jsonb,
  excluded_companies jsonb DEFAULT '[]'::jsonb,
  company_size jsonb DEFAULT '[]'::jsonb,
  industry jsonb DEFAULT '[]'::jsonb,
  date_posted text DEFAULT 'any',
  max_jobs_to_scrape integer DEFAULT 100,
  pages_to_scrape integer DEFAULT 10,
  weight_title_match integer DEFAULT 7,
  weight_skills_match integer DEFAULT 7,
  weight_salary_match integer DEFAULT 5,
  is_active boolean DEFAULT false,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Enable Row Level Security (RLS) on scrape_configs if not enabled
ALTER TABLE public.scrape_configs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow public read scrape_configs" ON public.scrape_configs;
CREATE POLICY "Allow public read scrape_configs" ON public.scrape_configs FOR SELECT USING (true);
GRANT SELECT ON public.scrape_configs TO anon;

-- 3. Create the scrape_runs table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.scrape_runs (
  run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  config_id bigint REFERENCES public.scrape_configs(id) ON DELETE SET NULL,
  status text DEFAULT 'pending',
  started_at timestamptz,
  finished_at timestamptz,
  total_found integer DEFAULT 0,
  new_jobs integer DEFAULT 0,
  pages_scraped integer DEFAULT 0,
  total_pages integer DEFAULT 0,
  errors integer DEFAULT 0,
  error_log jsonb DEFAULT '[]'::jsonb
);

-- Enable Row Level Security (RLS) on scrape_runs if not enabled
ALTER TABLE public.scrape_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow public read scrape_runs" ON public.scrape_runs;
CREATE POLICY "Allow public read scrape_runs" ON public.scrape_runs FOR SELECT USING (true);
GRANT SELECT ON public.scrape_runs TO anon;

-- 4. Recreate/Replace Views to reflect new schema structure
CREATE OR REPLACE VIEW public.job_dashboard AS
SELECT DISTINCT ON (j.job_id)
  j.job_id,
  j.title,
  c.name AS company_name,
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
  j.listed_time,
  j.original_listed_time,
  j.posted_at,
  j.scraped_at,
  j.discovered_at,
  j.relevance_score,
  j.matched_keywords
FROM public.jobs j
LEFT JOIN public.companies c ON j.company_id = c.company_id
LEFT JOIN LATERAL (
  SELECT min_salary, max_salary, pay_period, currency
  FROM public.salaries
  WHERE salaries.job_id = j.job_id
  ORDER BY salary_id DESC
  LIMIT 1
) s ON TRUE
WHERE j.scraped <> -2;

GRANT SELECT ON public.job_dashboard TO anon;

CREATE OR REPLACE VIEW public.job_details AS
SELECT
  j.job_id,
  j.title,
  j.description,
  j.skills_desc,
  c.name AS company_name,
  c.description AS company_description,
  c.url AS company_url,
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
  j.application_url,
  j.listed_time,
  j.original_listed_time,
  j.posted_at,
  j.scraped_at,
  j.discovered_at,
  j.relevance_score,
  j.matched_keywords
FROM public.jobs j
LEFT JOIN public.companies c ON j.company_id = c.company_id
LEFT JOIN LATERAL (
  SELECT min_salary, max_salary, pay_period, currency
  FROM public.salaries
  WHERE salaries.job_id = j.job_id
  ORDER BY salary_id DESC
  LIMIT 1
) s ON TRUE;

GRANT SELECT ON public.job_details TO anon;
