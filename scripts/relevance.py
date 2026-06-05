"""
Relevance scoring module.

Computes a 0-100 relevance score for a scraped job against a scrape config
profile.  The score is based on configurable weights and matching rules.
"""


def _lower_list(items):
    """Return a list of lowercased strings, filtering out None/empty."""
    if not items:
        return []
    if isinstance(items, str):
        return [items.lower()]
    return [str(s).lower() for s in items if s]


def _text_contains_any(text: str, keywords: list[str]) -> list[str]:
    """Return which keywords appear in text (case-insensitive)."""
    if not text or not keywords:
        return []
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def compute_relevance(job_data: dict, config: dict) -> tuple[int, list[str]]:
    """
    Score a job 0-100 based on config weights.

    Scoring breakdown:
    - Title keyword match:     base 30 pts × (weight_title_match / 10)
    - Required skills match:   base 25 pts × (weight_skills_match / 10)
                               (proportional to fraction matched)
    - Salary range match:      base 20 pts × (weight_salary_match / 10)
    - Experience level match:  15 pts (fixed)
    - Programming langs match: 10 pts (proportional to fraction matched)
    - Excluded keywords found: -50 pts (effective exclusion)

    Final score is clamped to 0-100.

    Parameters
    ----------
    job_data : dict
        Must contain keys like 'title', 'description', 'min_salary',
        'max_salary', 'formatted_experience_level'.  Missing keys are
        treated as empty / zero.
    config : dict
        The active scrape_config profile.

    Returns
    -------
    (score, matched_keywords) : tuple[int, list[str]]
    """
    matched = []
    raw_score = 0.0

    title = str(job_data.get('title') or '')
    description = str(job_data.get('description') or '')
    combined_text = f"{title} {description}"

    # ── Weight extraction (default 7 if missing) ────────────────────────
    w_title = min(max(int(config.get('weight_title_match', 7)), 0), 10)
    w_skills = min(max(int(config.get('weight_skills_match', 7)), 0), 10)
    w_salary = min(max(int(config.get('weight_salary_match', 5)), 0), 10)

    # ── 1. Title keyword match  (base 30 pts) ──────────────────────────
    title_keywords = _lower_list(config.get('keywords', []))
    job_titles_keywords = _lower_list(config.get('job_titles', []))
    all_title_keywords = title_keywords + job_titles_keywords

    if all_title_keywords:
        title_matches = _text_contains_any(title, all_title_keywords)
        if title_matches:
            # At least one match → full base points
            raw_score += 30.0 * (w_title / 10.0)
            matched.extend([f"title:{m}" for m in title_matches])

    # ── 2. Required skills match  (base 25 pts, proportional) ──────────
    required_skills = _lower_list(config.get('required_skills', []))
    if required_skills:
        skill_matches = _text_contains_any(combined_text, required_skills)
        fraction = len(skill_matches) / len(required_skills)
        raw_score += 25.0 * fraction * (w_skills / 10.0)
        matched.extend([f"skill:{m}" for m in skill_matches])

    # ── 3. Salary range match  (base 20 pts) ───────────────────────────
    expected_min = config.get('expected_pay_min')
    expected_max = config.get('expected_pay_max')
    job_min = job_data.get('min_salary')
    job_max = job_data.get('max_salary')

    if (expected_min or expected_max) and (job_min or job_max):
        # Treat missing bounds generously
        e_min = float(expected_min or 0)
        e_max = float(expected_max or float('inf'))
        j_min = float(job_min or 0)
        j_max = float(job_max or j_min)

        # Check overlap
        if j_max >= e_min and j_min <= e_max:
            raw_score += 20.0 * (w_salary / 10.0)
            matched.append(f"salary:{j_min}-{j_max}")

    # ── 4. Experience level match  (fixed 15 pts) ──────────────────────
    config_levels = _lower_list(config.get('experience_level', []))
    job_level = str(job_data.get('formatted_experience_level') or '').lower()

    if config_levels and job_level:
        # Normalize common variants
        level_map = {
            'internship': 'internship',
            'entry level': 'entry',
            'entry': 'entry',
            'associate': 'associate',
            'mid-senior level': 'mid-senior',
            'mid-senior': 'mid-senior',
            'director': 'director',
            'executive': 'executive',
        }
        normalized_job = level_map.get(job_level, job_level)
        normalized_config = [level_map.get(l, l) for l in config_levels]

        if normalized_job in normalized_config:
            raw_score += 15.0
            matched.append(f"experience:{job_level}")

    # ── 5. Programming languages match  (10 pts, proportional) ─────────
    languages = _lower_list(config.get('programming_languages', []))
    if languages:
        lang_matches = _text_contains_any(combined_text, languages)
        fraction = len(lang_matches) / len(languages)
        raw_score += 10.0 * fraction
        matched.extend([f"lang:{m}" for m in lang_matches])

    # ── 6. Excluded keywords penalty  (-50 pts) ────────────────────────
    excluded = _lower_list(config.get('excluded_keywords', []))
    if excluded:
        excluded_matches = _text_contains_any(combined_text, excluded)
        if excluded_matches:
            raw_score -= 50.0
            matched.extend([f"excluded:{m}" for m in excluded_matches])

    # ── Normalize to 0-100 ─────────────────────────────────────────────
    score = max(0, min(100, round(raw_score)))

    return score, matched
