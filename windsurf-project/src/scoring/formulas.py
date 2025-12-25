"""
Scoring Formulas Documentation

This module documents the scoring logic used in the lead scoring engine.
It serves as both documentation and a reference implementation.
"""

# =============================================================================
# LEAD SCORING FORMULA
# =============================================================================
"""
TOTAL SCORE CALCULATION
=======================

The total lead score is a weighted sum of five component scores:

    TOTAL_SCORE = Σ (COMPONENT_SCORE × WEIGHT)

Where:
    - Each COMPONENT_SCORE is normalized to 0-100
    - WEIGHTS sum to 1.0
    - TOTAL_SCORE ranges from 0-100

Default Weights:
    - Role Match:      0.30 (30%)
    - Tech Match:      0.25 (25%)
    - Hiring Signals:  0.20 (20%)
    - Company Signals: 0.15 (15%)
    - Recency:         0.10 (10%)


COMPONENT FORMULAS
==================

1. ROLE MATCH SCORE (0-100)
---------------------------
Measures how well job titles match target roles.

    ROLE_SCORE = max(ROLE_WEIGHT × SENIORITY_MULTIPLIER × 100) for each title

    Where:
    - ROLE_WEIGHT: 1.0 for primary roles, 0.7-0.9 for secondary
    - SENIORITY_MULTIPLIER:
        - Principal/Distinguished: 1.3
        - Staff: 1.2
        - Lead: 1.15
        - Senior: 1.1
        - Mid: 1.0
        - Junior: 0.5

    Example:
    - "Senior Data Engineer" → 1.0 × 1.1 × 100 = 110 → capped at 100
    - "Software Engineer" → 0.7 × 1.0 × 100 = 70


2. TECH MATCH SCORE (0-100)
---------------------------
Measures alignment with target tech stack.

    TECH_SCORE = min((Σ TECH_WEIGHTS) / 5.0 × 100, 100)

    Where:
    - TECH_WEIGHTS: 0.5-1.0 per matched technology
    - Normalization: 5 high-weight (1.0) matches = 100

    Example:
    - Matched: Python(1.0), Spark(1.0), Airflow(1.0), AWS(0.9)
    - Sum: 3.9
    - Score: (3.9 / 5.0) × 100 = 78


3. HIRING SIGNALS SCORE (0-100)
-------------------------------
Measures active hiring indicators.

    HIRING_SCORE = min(Σ SIGNAL_POINTS, 100)

    Signal Points:
    - Strong signals ("we're hiring", "open positions"): +30 each
    - Active job listings detected: +40
    - Has careers page: +20

    Example:
    - "We're hiring" found: +30
    - Active listings: +40
    - Careers page exists: +20
    - Total: 90


4. COMPANY SIGNALS SCORE (0-100)
--------------------------------
Measures company health and growth indicators.

    COMPANY_SCORE = min(Σ SIGNAL_POINTS, 100)

    Signal Points:
    - Funding signals (Series A/B/C, raised $X): +40
    - Growth signals (expanding, scaling): +30
    - Remote indicators: +20
    - Contact emails available: +10

    Example:
    - "Series B" mentioned: +40
    - "Growing team" found: +30
    - "Remote-first": +20
    - Total: 90


5. RECENCY SCORE (0-100)
------------------------
Measures data freshness.

    If AGE_DAYS <= FRESH_DAYS:
        RECENCY_SCORE = 100

    Elif AGE_DAYS >= STALE_DAYS:
        RECENCY_SCORE = 0

    Else:
        RECENCY_SCORE = 100 × (1 - (AGE_DAYS - FRESH_DAYS) / (STALE_DAYS - FRESH_DAYS))

    Default values:
    - FRESH_DAYS = 7
    - STALE_DAYS = 30

    Example:
    - Data from 3 days ago: 100
    - Data from 15 days ago: 100 × (1 - (15-7)/(30-7)) = 65
    - Data from 45 days ago: 0


PRIORITY CLASSIFICATION
=======================

Based on TOTAL_SCORE:

    HIGH:   score >= 70
    MEDIUM: score >= 40 AND score < 70
    LOW:    score < 40


EXAMPLE CALCULATION
===================

Company: acme.io
- Job titles: ["Senior Data Engineer", "ML Engineer"]
- Tech: ["Python", "Spark", "Airflow", "Kubernetes"]
- Signals: ["we're hiring", "series b"]
- Remote: ["remote-first"]
- Has careers page: Yes
- Active listings: Yes
- Last updated: 2 days ago

Component Scores:
- Role: max(1.0×1.1×100, 1.0×1.0×100) = 100
- Tech: (1.0+1.0+1.0+0.8)/5×100 = 76
- Hiring: 30+40+20 = 90
- Company: 40+20 = 60
- Recency: 100

Weighted Total:
- 100×0.30 = 30.0
- 76×0.25 = 19.0
- 90×0.20 = 18.0
- 60×0.15 = 9.0
- 100×0.10 = 10.0
- TOTAL = 86.0

Priority: HIGH (86 >= 70)
"""


# =============================================================================
# PSEUDO-CODE IMPLEMENTATION
# =============================================================================

def calculate_lead_score(company_data: dict, config: dict) -> dict:
    """
    Pseudo-code for lead scoring calculation.
    
    Args:
        company_data: Dictionary containing:
            - domain: str
            - job_titles: List[str]
            - tech_keywords: List[str]
            - hiring_signals: List[str]
            - remote_indicators: List[str]
            - has_careers_page: bool
            - has_active_listings: bool
            - contact_emails: List[str]
            - last_updated: datetime
        config: Dictionary containing:
            - weights: dict with role, tech, hiring, company, recency
            - role_patterns: dict mapping pattern to weight
            - seniority_multipliers: dict mapping level to multiplier
            - tech_weights: dict mapping tech to weight
            - fresh_days: int
            - stale_days: int
            - high_priority_threshold: int
            - min_lead_threshold: int
    
    Returns:
        Dictionary with total_score, priority, component_scores, matched_items
    """
    from datetime import datetime
    
    # 1. Role Match Score
    role_score = 0
    matched_roles = []
    for title in company_data.get('job_titles', []):
        for pattern, weight in config.get('role_patterns', {}).items():
            if pattern in title.lower():
                multiplier = get_seniority_multiplier(title, config.get('seniority_multipliers', {}))
                score = min(weight * multiplier * 100, 100)
                if score > role_score:
                    role_score = score
                matched_roles.append(title)
    
    # 2. Tech Match Score
    tech_sum = 0
    matched_techs = []
    for tech in company_data.get('tech_keywords', []):
        tech_weights = config.get('tech_weights', {})
        if tech.lower() in tech_weights:
            tech_sum += tech_weights[tech.lower()]
            matched_techs.append(tech)
    tech_score = min((tech_sum / 5.0) * 100, 100)
    
    # 3. Hiring Signals Score
    hiring_score = 0
    hiring_signals = company_data.get('hiring_signals', [])
    if has_strong_hiring_signal(hiring_signals):
        hiring_score += 30
    if company_data.get('has_active_listings', False):
        hiring_score += 40
    if company_data.get('has_careers_page', False):
        hiring_score += 20
    hiring_score = min(hiring_score, 100)
    
    # 4. Company Signals Score
    company_score = 0
    if has_funding_signal(hiring_signals):
        company_score += 40
    if has_growth_signal(hiring_signals):
        company_score += 30
    if company_data.get('remote_indicators'):
        company_score += 20
    if company_data.get('contact_emails'):
        company_score += 10
    company_score = min(company_score, 100)
    
    # 5. Recency Score
    last_updated = company_data.get('last_updated')
    if last_updated:
        age_days = (datetime.now() - last_updated).days
    else:
        age_days = 15  # Default to middle value
    
    fresh_days = config.get('fresh_days', 7)
    stale_days = config.get('stale_days', 30)
    
    if age_days <= fresh_days:
        recency_score = 100
    elif age_days >= stale_days:
        recency_score = 0
    else:
        decay_range = stale_days - fresh_days
        days_past_fresh = age_days - fresh_days
        recency_score = 100 * (1 - days_past_fresh / decay_range)
    
    # Calculate weighted total
    weights = config.get('weights', {})
    total_score = (
        role_score * weights.get('role', 0.30) +
        tech_score * weights.get('tech', 0.25) +
        hiring_score * weights.get('hiring', 0.20) +
        company_score * weights.get('company', 0.15) +
        recency_score * weights.get('recency', 0.10)
    )
    
    # Determine priority
    high_threshold = config.get('high_priority_threshold', 70)
    min_threshold = config.get('min_lead_threshold', 40)
    
    if total_score >= high_threshold:
        priority = 'high'
    elif total_score >= min_threshold:
        priority = 'medium'
    else:
        priority = 'low'
    
    return {
        'total_score': total_score,
        'priority': priority,
        'component_scores': {
            'role': role_score,
            'tech': tech_score,
            'hiring': hiring_score,
            'company': company_score,
            'recency': recency_score
        },
        'matched_items': {
            'roles': matched_roles,
            'techs': matched_techs
        }
    }


# Helper functions (pseudo-code)
def get_seniority_multiplier(title: str, multipliers: dict) -> float:
    """Get seniority multiplier from title."""
    title_lower = title.lower()
    for level, mult in multipliers.items():
        if level in title_lower:
            return mult
    return 1.0


def has_strong_hiring_signal(signals: list) -> bool:
    """Check for strong hiring signals."""
    strong_patterns = ["we're hiring", "now hiring", "open positions"]
    for signal in signals:
        for pattern in strong_patterns:
            if pattern in signal.lower():
                return True
    return False


def has_funding_signal(signals: list) -> bool:
    """Check for funding signals."""
    funding_patterns = ["series", "raised", "backed", "funding"]
    for signal in signals:
        for pattern in funding_patterns:
            if pattern in signal.lower():
                return True
    return False


def has_growth_signal(signals: list) -> bool:
    """Check for growth signals."""
    growth_patterns = ["growing", "expanding", "scaling"]
    for signal in signals:
        for pattern in growth_patterns:
            if pattern in signal.lower():
                return True
    return False
