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
  discovered_at timestamptz not null default now()
);

create table if not exists public.skills (
  skill_abr text primary key,
  skill_name text
);

create table if not exists public.job_skills (
  job_id bigint references public.jobs(job_id) on delete cascade,
  skill_abr text references public.skills(skill_abr) on delete cascade,
  primary key (job_id, skill_abr)
);

create table if not exists public.industries (
  industry_id bigint primary key,
  industry_name text
);

create table if not exists public.job_industries (
  job_id bigint references public.jobs(job_id) on delete cascade,
  industry_id bigint references public.industries(industry_id) on delete cascade,
  primary key (job_id, industry_id)
);

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

create table if not exists public.benefits (
  job_id bigint not null references public.jobs(job_id) on delete cascade,
  inferred integer not null,
  type text not null,
  primary key (job_id, type)
);

create table if not exists public.employee_counts (
  company_id bigint not null references public.companies(company_id) on delete cascade,
  employee_count integer,
  follower_count integer,
  time_recorded bigint not null,
  primary key (employee_count, company_id)
);

create table if not exists public.company_specialities (
  company_id bigint not null references public.companies(company_id) on delete cascade,
  speciality text not null,
  primary key (company_id, speciality)
);

create table if not exists public.company_industries (
  company_id bigint not null references public.companies(company_id) on delete cascade,
  industry text not null,
  primary key (company_id, industry)
);

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
  j.discovered_at
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
  j.discovered_at
from public.jobs j
left join public.companies c on j.company_id = c.company_id
left join lateral (
  select min_salary, max_salary, pay_period, currency
  from public.salaries
  where salaries.job_id = j.job_id
  order by salary_id desc
  limit 1
) s on true;

alter table public.jobs enable row level security;
alter table public.companies enable row level security;
alter table public.salaries enable row level security;

drop policy if exists "Allow public read jobs" on public.jobs;
create policy "Allow public read jobs" on public.jobs for select using (true);

drop policy if exists "Allow public read companies" on public.companies;
create policy "Allow public read companies" on public.companies for select using (true);

drop policy if exists "Allow public read salaries" on public.salaries;
create policy "Allow public read salaries" on public.salaries for select using (true);

grant usage on schema public to anon;
grant select on public.job_dashboard to anon;
grant select on public.job_details to anon;
