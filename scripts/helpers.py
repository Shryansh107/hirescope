import pandas as pd

variable_paths = pd.read_csv('json_paths/data_variables.csv')
included_paths = pd.read_csv('json_paths/included_variables.csv')

size_ranges = {(None, 10): 0, (11, 50): 1, (51, 200): 2, (201, 500): 3, (501, 1000): 4, (1001, 5000): 5, (5001, 10000): 6, (10001, None): 7}

def strip_val(val, cat):
    if cat == 0 or val == None:
        return val
    elif cat == 1:
        return val.split(':')[-1]
    elif cat == 2:
        return val.split('.')[-1]
    else:
        raise ValueError

def get_value_by_path(dictionary, path):
    keys = path.strip("[]'").split("']['")
    for key in keys:
        if not dictionary or key not in dictionary:
            return False
        dictionary = dictionary[key]
    return dictionary

def clean_job_postings(all_jobs):
    all_cleaned_postings = dict()
    for job_id, job_info in all_jobs.items():
        if job_info == -1:
            posting = {'error': job_info}
        else:
            posting = {'jobs': {}, 'companies': {}, 'salaries': {}, 'benefits': {}, 'industries': {}, 'skills': {}, 'employee_counts': {}, 'company_industries': {}, 'company_specialities': {}}
            for idx, row in variable_paths.iterrows():
                value = get_value_by_path(job_info, row['path'])
                if value:
                    posting[row['table']][row['name']] = strip_val(value, row['strip'])

            for idx, row in included_paths.iterrows():
                for into_type in job_info['included']:
                    if strip_val(into_type.get('$type'), 2) == row['type']:
                        if row['name'] == 'company_size':
                            company_size_info = get_value_by_path(into_type, row['path'])
                            if company_size_info:
                                posting[row['table']][row['name']] = size_ranges.get((company_size_info.get('start'), company_size_info.get('end')))
                        else:
                            value = get_value_by_path(into_type, row['path'])
                            posting[row['table']][row['name']] = strip_val(value, row['strip'])


        # posting['companies']['size_range'] = size_ranges.get(job_info['included'][-1])
        all_cleaned_postings[job_id] = posting

    return all_cleaned_postings


def matches_config_filters(title: str, config: dict) -> bool:
    """
    Check whether a job title passes the config-based filters.

    Returns True if the job should be included, False if excluded.

    Checks:
    - excluded_keywords: if any appear in the title → exclude
    - job_titles / keywords: if specified, at least one must match → include
      (if neither is specified, all titles are included)
    """
    if not title:
        return False

    title_lower = title.lower()

    # Check excluded keywords
    excluded = config.get('excluded_keywords', [])
    if excluded and isinstance(excluded, list):
        for kw in excluded:
            if kw and kw.lower() in title_lower:
                return False

    # Check if title matches at least one keyword or job title
    keywords = config.get('keywords', [])
    job_titles = config.get('job_titles', [])

    # Combine all positive-match terms
    match_terms = []
    if isinstance(keywords, list):
        match_terms.extend(keywords)
    if isinstance(job_titles, list):
        match_terms.extend(job_titles)

    # If no positive filters are set, accept everything
    if not match_terms:
        return True

    # At least one term must appear in the title
    for term in match_terms:
        if term and term.lower() in title_lower:
            return True

    return False
