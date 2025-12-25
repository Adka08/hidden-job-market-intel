# Data Schema Documentation

## CSV Schemas

### 1. Discovered Domains (`domains_{date}.csv`)

Raw output from Google dorking discovery.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `domain` | string | Root domain | `acme.io` |
| `source_query` | string | Dork query that found it | `inurl:careers "data engineer"` |
| `url` | string | Full URL from search result | `https://acme.io/careers` |
| `title` | string | Page title from search | `Careers | Acme` |
| `snippet` | string | Search result snippet | `Join our data team...` |
| `category` | string | Dork category | `careers`, `hiring_signals` |
| `discovered_at` | datetime | ISO timestamp | `2024-01-15T10:30:00Z` |

```csv
domain,source_query,url,title,snippet,category,discovered_at
acme.io,"inurl:careers ""data engineer""",https://acme.io/careers,Careers | Acme,Join our data team...,careers,2024-01-15T10:30:00Z
```

---

### 2. Scraped Pages (`pages.csv`)

Individual pages scraped from company websites.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `url` | string | Full page URL | `https://acme.io/careers` |
| `domain` | string | Root domain | `acme.io` |
| `title` | string | Page title | `Careers at Acme` |
| `page_type` | string | Detected type | `careers`, `about`, `team` |
| `content_hash` | string | MD5 hash for change detection | `a1b2c3d4...` |
| `status_code` | int | HTTP status | `200` |
| `scraped_at` | datetime | ISO timestamp | `2024-01-15T11:00:00Z` |
| `job_titles` | json | Extracted job titles | `["Senior Data Engineer"]` |
| `tech_keywords` | json | Matched tech keywords | `["python", "spark"]` |
| `hiring_signals` | json | Detected hiring signals | `["hiring:we're hiring"]` |
| `remote_indicators` | json | Remote work indicators | `["remote"]` |
| `contact_emails` | json | Public contact emails | `["careers@acme.io"]` |
| `has_apply_button` | bool | Apply CTA detected | `true` |
| `has_job_listings` | bool | Multiple listings found | `true` |

```csv
url,domain,title,page_type,content_hash,status_code,scraped_at,job_titles,tech_keywords,hiring_signals,remote_indicators,contact_emails,has_apply_button,has_job_listings
https://acme.io/careers,acme.io,Careers at Acme,careers,a1b2c3d4,200,2024-01-15T11:00:00Z,"[""Senior Data Engineer""]","[""python"",""spark""]","[""hiring:we're hiring""]","[""remote""]","[""careers@acme.io""]",true,true
```

---

### 3. Company Profiles (`profiles.csv`)

Aggregated company data from all scraped pages.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `domain` | string | Root domain | `acme.io` |
| `name` | string | Company name | `Acme Inc` |
| `careers_url` | string | Careers page URL | `https://acme.io/careers` |
| `job_titles` | json | All job titles found | `["Senior Data Engineer", "ML Engineer"]` |
| `tech_keywords` | json | All tech keywords | `["python", "spark", "aws"]` |
| `hiring_signals` | json | All hiring signals | `["hiring:we're hiring", "funding:series b"]` |
| `remote_indicators` | json | Remote indicators | `["remote", "distributed"]` |
| `contact_emails` | json | Contact emails | `["careers@acme.io"]` |
| `pages_scraped` | int | Number of pages scraped | `3` |
| `has_active_listings` | bool | Active job listings | `true` |
| `first_seen` | datetime | First discovery date | `2024-01-10T08:00:00Z` |
| `last_updated` | datetime | Last scrape date | `2024-01-15T11:00:00Z` |

---

### 4. Scored Leads (`scored_leads_{date}.csv`)

Final scored and prioritized leads.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `domain` | string | Root domain | `acme.io` |
| `total_score` | float | Overall score (0-100) | `78.5` |
| `priority` | string | Priority level | `high`, `medium`, `low` |
| `role_score` | float | Role match score | `100.0` |
| `tech_score` | float | Tech match score | `76.0` |
| `hiring_score` | float | Hiring signals score | `90.0` |
| `company_score` | float | Company signals score | `60.0` |
| `recency_score` | float | Data freshness score | `100.0` |
| `matched_roles` | json | Matched job titles | `["Senior Data Engineer"]` |
| `matched_techs` | json | Matched technologies | `["python", "spark"]` |
| `matched_signals` | json | All matched signals | `["hiring:we're hiring"]` |
| `scored_at` | datetime | Scoring timestamp | `2024-01-15T12:00:00Z` |

```csv
domain,total_score,priority,role_score,tech_score,hiring_score,company_score,recency_score,matched_roles,matched_techs,matched_signals,scored_at
acme.io,78.5,high,100.0,76.0,90.0,60.0,100.0,"[""Senior Data Engineer""]","[""python"",""spark""]","[""hiring:we're hiring""]",2024-01-15T12:00:00Z
```

---

## SQLite Database Schema

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│    domains      │       │     pages       │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │
│ domain (UNIQUE) │◄──────│ domain (FK)     │
│ source_query    │       │ url (UNIQUE)    │
│ category        │       │ title           │
│ discovered_at   │       │ page_type       │
│ status          │       │ content_hash    │
│ notes           │       │ status_code     │
└────────┬────────┘       │ scraped_at      │
         │                │ job_titles      │
         │                │ tech_keywords   │
         │                │ hiring_signals  │
         │                │ ...             │
         │                └─────────────────┘
         │
         │                ┌─────────────────┐
         │                │   companies     │
         │                ├─────────────────┤
         ├───────────────►│ id (PK)         │
         │                │ domain (FK,UNQ) │
         │                │ name            │
         │                │ careers_url     │
         │                │ all_job_titles  │
         │                │ all_tech_kw     │
         │                │ ...             │
         │                └─────────────────┘
         │
         │                ┌─────────────────┐
         │                │    scores       │
         │                ├─────────────────┤
         ├───────────────►│ id (PK)         │
         │                │ domain (FK)     │
         │                │ total_score     │
         │                │ priority        │
         │                │ role_score      │
         │                │ tech_score      │
         │                │ ...             │
         │                │ scored_at       │
         │                └─────────────────┘
         │
         │                ┌─────────────────┐
         │                │    changes      │
         │                ├─────────────────┤
         └───────────────►│ id (PK)         │
                          │ domain (FK)     │
                          │ url             │
                          │ change_type     │
                          │ old_value       │
                          │ new_value       │
                          │ detected_at     │
                          └─────────────────┘
```

### Table Definitions

```sql
-- Discovered domains from Google dorking
CREATE TABLE domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    source_query TEXT,
    category TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending, scraped, blocked, error
    notes TEXT
);

-- Individual scraped pages
CREATE TABLE pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    domain TEXT NOT NULL,
    title TEXT,
    page_type TEXT,
    content_hash TEXT,
    status_code INTEGER,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    job_titles TEXT,        -- JSON array
    tech_keywords TEXT,     -- JSON array
    hiring_signals TEXT,    -- JSON array
    remote_indicators TEXT, -- JSON array
    contact_emails TEXT,    -- JSON array
    has_apply_button BOOLEAN DEFAULT FALSE,
    has_job_listings BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (domain) REFERENCES domains(domain)
);

-- Aggregated company profiles
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    name TEXT,
    careers_url TEXT,
    all_job_titles TEXT,      -- JSON array
    all_tech_keywords TEXT,   -- JSON array
    all_hiring_signals TEXT,  -- JSON array
    all_remote_indicators TEXT, -- JSON array
    all_contact_emails TEXT,  -- JSON array
    pages_scraped INTEGER DEFAULT 0,
    has_active_listings BOOLEAN DEFAULT FALSE,
    first_seen TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain) REFERENCES domains(domain)
);

-- Lead scores with history
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    total_score REAL,
    priority TEXT,
    role_score REAL,
    tech_score REAL,
    hiring_score REAL,
    company_score REAL,
    recency_score REAL,
    matched_roles TEXT,   -- JSON array
    matched_techs TEXT,   -- JSON array
    matched_signals TEXT, -- JSON array
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain) REFERENCES domains(domain)
);

-- Change detection log
CREATE TABLE changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    url TEXT,
    change_type TEXT,  -- new_listing, removed_listing, content_change, score_change
    old_value TEXT,    -- JSON
    new_value TEXT,    -- JSON
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain) REFERENCES domains(domain)
);

-- Indexes
CREATE INDEX idx_domains_status ON domains(status);
CREATE INDEX idx_pages_domain ON pages(domain);
CREATE INDEX idx_companies_domain ON companies(domain);
CREATE INDEX idx_scores_domain ON scores(domain);
CREATE INDEX idx_scores_priority ON scores(priority);
CREATE INDEX idx_changes_domain ON changes(domain);
```

---

## Sample Queries

### Get High-Priority Leads

```sql
SELECT 
    c.domain,
    c.name,
    c.careers_url,
    s.total_score,
    s.priority,
    c.all_job_titles,
    c.all_tech_keywords
FROM companies c
JOIN scores s ON c.domain = s.domain
WHERE s.priority = 'high'
AND s.scored_at = (
    SELECT MAX(scored_at) FROM scores WHERE domain = c.domain
)
ORDER BY s.total_score DESC;
```

### Get Recent Changes

```sql
SELECT 
    domain,
    change_type,
    old_value,
    new_value,
    detected_at
FROM changes
WHERE detected_at >= datetime('now', '-7 days')
ORDER BY detected_at DESC;
```

### Get Companies with Specific Tech

```sql
SELECT domain, name, all_tech_keywords
FROM companies
WHERE all_tech_keywords LIKE '%spark%'
   OR all_tech_keywords LIKE '%airflow%';
```

### Score Trend for a Domain

```sql
SELECT 
    domain,
    total_score,
    scored_at
FROM scores
WHERE domain = 'acme.io'
ORDER BY scored_at;
```
