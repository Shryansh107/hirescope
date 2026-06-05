-- ============================================================
-- DANGER: Drops all tables and views, deleting all data!
-- ============================================================

DROP VIEW IF EXISTS public.job_dashboard CASCADE;
DROP VIEW IF EXISTS public.job_details CASCADE;

DROP TABLE IF EXISTS public.job_skills CASCADE;
DROP TABLE IF EXISTS public.job_industries CASCADE;
DROP TABLE IF EXISTS public.salaries CASCADE;
DROP TABLE IF EXISTS public.benefits CASCADE;
DROP TABLE IF EXISTS public.employee_counts CASCADE;
DROP TABLE IF EXISTS public.company_specialities CASCADE;
DROP TABLE IF EXISTS public.company_industries CASCADE;
DROP TABLE IF EXISTS public.jobs CASCADE;
DROP TABLE IF EXISTS public.companies CASCADE;
DROP TABLE IF EXISTS public.skills CASCADE;
DROP TABLE IF EXISTS public.industries CASCADE;
DROP TABLE IF EXISTS public.scrape_runs CASCADE;
DROP TABLE IF EXISTS public.scrape_configs CASCADE;

-- ============================================================
-- Companies (must be created before jobs due to FK)
-- ============================================================
create table if not exists public.companies (
  company_id bigint primary key,
  name text,
  description text,
  company_size integer,
  state text,
  country text,
  city text,
  zip_code text,
  address text,
  url text
);

-- ============================================================
-- Jobs
-- ============================================================
create table if not exists public.jobs (
  job_id bigint primary key,
  scraped integer not null default 0,
  company_id bigint references public.companies(company_id),
  work_type text,
  formatted_work_type text,
  location text,
  job_posting_url text,
  applies integer,
  original_listed_time text,
  remote_allowed integer,
  application_url text,
  application_type text,
  expiry text,
  inferred_benefits text,
  closed_time text,
  formatted_experience_level text,
  years_experience integer,
  description text,
  title text,
  skills_desc text,
  views integer,
  job_region text,
  listed_time text,
  degree text,
  posting_domain text,
  sponsored boolean,
  posted_at timestamptz,
  scraped_at timestamptz,
  discovered_at timestamptz not null default now(),
  relevance_score integer,
  matched_keywords jsonb,
  scrape_run_id bigint
);

-- ============================================================
-- Skills
-- ============================================================
create table if not exists public.skills (
  skill_abr text primary key,
  skill_name text
);

create table if not exists public.job_skills (
  job_id bigint references public.jobs(job_id) on delete cascade,
  skill_abr text references public.skills(skill_abr) on delete cascade,
  primary key (job_id, skill_abr)
);

-- ============================================================
-- Industries
-- ============================================================
create table if not exists public.industries (
  industry_id bigint primary key,
  industry_name text
);

create table if not exists public.job_industries (
  job_id bigint references public.jobs(job_id) on delete cascade,
  industry_id bigint references public.industries(industry_id) on delete cascade,
  primary key (job_id, industry_id)
);

-- ============================================================
-- Salaries
-- ============================================================
create table if not exists public.salaries (
  salary_id bigint generated always as identity primary key,
  job_id bigint not null references public.jobs(job_id) on delete cascade,
  max_salary double precision,
  med_salary double precision,
  min_salary double precision,
  pay_period text,
  currency text,
  compensation_type text
);

create index if not exists salaries_job_id_idx on public.salaries(job_id);

-- ============================================================
-- Benefits
-- ============================================================
create table if not exists public.benefits (
  job_id bigint not null references public.jobs(job_id) on delete cascade,
  inferred integer not null,
  type text not null,
  primary key (job_id, type)
);

-- ============================================================
-- Employee counts
-- ============================================================
create table if not exists public.employee_counts (
  company_id bigint not null references public.companies(company_id) on delete cascade,
  employee_count integer,
  follower_count integer,
  time_recorded bigint not null,
  primary key (employee_count, company_id)
);

-- ============================================================
-- Company specialities
-- ============================================================
create table if not exists public.company_specialities (
  company_id bigint not null references public.companies(company_id) on delete cascade,
  speciality text not null,
  primary key (company_id, speciality)
);

-- ============================================================
-- Company industries
-- ============================================================
create table if not exists public.company_industries (
  company_id bigint not null references public.companies(company_id) on delete cascade,
  industry text not null,
  primary key (company_id, industry)
);

-- ============================================================
-- Scrape Configuration Profiles
-- ============================================================
create table if not exists public.scrape_configs (
  id bigint generated always as identity primary key,
  profile_name text not null,
  keywords jsonb default '[]'::jsonb,
  job_titles jsonb default '[]'::jsonb,
  excluded_keywords jsonb default '[]'::jsonb,
  location text default '',
  remote_filter text default 'any',
  job_type jsonb default '[]'::jsonb,
  experience_level jsonb default '[]'::jsonb,
  years_of_experience_min integer,
  years_of_experience_max integer,
  expected_pay_min integer,
  expected_pay_max integer,
  pay_currency text default 'USD',
  required_skills jsonb default '[]'::jsonb,
  preferred_skills jsonb default '[]'::jsonb,
  programming_languages jsonb default '[]'::jsonb,
  company_names jsonb default '[]'::jsonb,
  excluded_companies jsonb default '[]'::jsonb,
  company_size jsonb default '[]'::jsonb,
  industry jsonb default '[]'::jsonb,
  date_posted text default 'any',
  max_jobs_to_scrape integer default 100,
  pages_to_scrape integer default 10,
  weight_title_match integer default 7,
  weight_skills_match integer default 7,
  weight_salary_match integer default 5,
  is_active boolean default false,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- ============================================================
-- Scrape Run History
-- ============================================================
create table if not exists public.scrape_runs (
  run_id bigint generated always as identity primary key,
  config_id bigint references public.scrape_configs(id) on delete set null,
  status text default 'pending',
  started_at timestamptz,
  finished_at timestamptz,
  total_found integer default 0,
  new_jobs integer default 0,
  pages_scraped integer default 0,
  total_pages integer default 0,
  errors integer default 0,
  error_log jsonb default '[]'::jsonb
);

-- ============================================================
-- Views
-- ============================================================
create or replace view public.job_dashboard as
select
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
  j.job_posting_url,
  j.listed_time,
  j.original_listed_time,
  j.posted_at,
  j.scraped_at,
  j.discovered_at,
  j.relevance_score,
  j.matched_keywords
from public.jobs j
left join public.companies c on j.company_id = c.company_id
left join lateral (
  select min_salary, max_salary, pay_period, currency
  from public.salaries
  where salaries.job_id = j.job_id
  order by salary_id desc
  limit 1
) s on true
where j.scraped <> -2;

create or replace view public.job_details as
select
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
  j.application_url,
  j.listed_time,
  j.original_listed_time,
  j.posted_at,
  j.scraped_at,
  j.discovered_at,
  j.relevance_score,
  j.matched_keywords
from public.jobs j
left join public.companies c on j.company_id = c.company_id
left join lateral (
  select min_salary, max_salary, pay_period, currency
  from public.salaries
  where salaries.job_id = j.job_id
  order by salary_id desc
  limit 1
) s on true;

-- ============================================================
-- Row Level Security (RLS)
-- ============================================================
alter table public.jobs enable row level security;
alter table public.companies enable row level security;
alter table public.salaries enable row level security;
alter table public.scrape_configs enable row level security;
alter table public.scrape_runs enable row level security;

-- Public read policies
drop policy if exists "Allow public read jobs" on public.jobs;
create policy "Allow public read jobs" on public.jobs for select using (true);

drop policy if exists "Allow public read companies" on public.companies;
create policy "Allow public read companies" on public.companies for select using (true);

drop policy if exists "Allow public read salaries" on public.salaries;
create policy "Allow public read salaries" on public.salaries for select using (true);

drop policy if exists "Allow public read scrape_configs" on public.scrape_configs;
create policy "Allow public read scrape_configs" on public.scrape_configs for select using (true);

drop policy if exists "Allow public read scrape_runs" on public.scrape_runs;
create policy "Allow public read scrape_runs" on public.scrape_runs for select using (true);

-- Grant schema usage and select permissions to anon
grant usage on schema public to anon;
grant select on public.job_dashboard to anon;
grant select on public.job_details to anon;
grant select on public.scrape_configs to anon;
grant select on public.scrape_runs to anon;
