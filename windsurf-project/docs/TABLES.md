# System Reference Tables

## Layer Overview

### Discovery Layer (Google Dorking Engine)

| Component | Input | Output | Purpose |
|-----------|-------|--------|---------|
| `dork_engine.py` | Config YAML files | Google search URLs | Generate targeted search queries |
| `DorkTemplate` | Role/tech variables | Formatted query string | Template-based query building |
| `DiscoveredDomain` | Search results | Domain records | Track discovered companies |

### Extraction Layer (Scraping + Intelligence)

| Component | Input | Output | Purpose |
|-----------|-------|--------|---------|
| `scraper.py` | Domain list | Pages CSV, Profiles CSV | Extract job-relevant data |
| `robots_checker.py` | URL | Allow/Deny decision | Ensure compliance |
| `rate_limiter.py` | Domain | Delay timing | Prevent server overload |
| `PageTypeDetector` | URL + HTML | Page classification | Identify careers pages |
| `TechKeywordExtractor` | Page text | Tech keyword list | Match target stack |
| `JobTitleExtractor` | HTML | Job title list | Find open roles |
| `HiringSignalExtractor` | Page text | Signal list | Detect active hiring |
| `EmailExtractor` | Page text | Email list | Find contact info |

### Scoring Layer (Lead Qualification)

| Component | Input | Output | Purpose |
|-----------|-------|--------|---------|
| `scorer.py` | Company profiles | Scored leads CSV | Prioritize leads |
| `LeadScore` | Component scores | Total score + priority | Aggregate scoring |
| `formulas.py` | - | - | Document scoring logic |

---

## Dork Categories

| Category | Purpose | Example Dork | Best For |
|----------|---------|--------------|----------|
| `careers` | Find career pages | `site:*.com inurl:careers "{role}"` | Daily discovery |
| `hiring_signals` | Detect active hiring | `"we're hiring" "{role}"` | High-intent leads |
| `tech_stack` | Match technologies | `"our stack" "{tech}"` | Stack alignment |
| `funding` | Find funded companies | `"series b" "hiring"` | Growth companies |
| `remote` | Find remote roles | `"remote-first" "{role}"` | Remote preference |

---

## Scoring Weights

| Component | Default Weight | Score Range | What It Measures |
|-----------|---------------|-------------|------------------|
| Role Match | 30% | 0-100 | Job title alignment |
| Tech Match | 25% | 0-100 | Technology stack fit |
| Hiring Signals | 20% | 0-100 | Active hiring indicators |
| Company Signals | 15% | 0-100 | Funding, growth, remote |
| Recency | 10% | 0-100 | Data freshness |

---

## Priority Classification

| Priority | Score Range | Action | Volume |
|----------|-------------|--------|--------|
| **High** | 70-100 | Immediate action, apply ASAP | ~10-15% of leads |
| **Medium** | 40-69 | Research further, monitor | ~30-40% of leads |
| **Low** | 0-39 | Archive, low relevance | ~50% of leads |

---

## Tech Keywords by Category

### Languages (Weight)
| Keyword | Weight | Aliases |
|---------|--------|---------|
| Python | 1.0 | py, python3 |
| SQL | 1.0 | postgresql, mysql, bigquery |
| Go | 0.8 | golang |
| Scala | 0.8 | - |
| Java | 0.7 | jvm |
| Rust | 0.6 | - |

### Data/ML Frameworks (Weight)
| Keyword | Weight | Aliases |
|---------|--------|---------|
| Spark | 1.0 | pyspark, apache spark |
| Airflow | 1.0 | apache airflow |
| PyTorch | 1.0 | torch |
| Databricks | 1.0 | - |
| Kafka | 0.9 | apache kafka |
| dbt | 0.9 | data build tool |
| MLflow | 0.9 | - |
| Huggingface | 1.0 | transformers |

### Infrastructure (Weight)
| Keyword | Weight | Aliases |
|---------|--------|---------|
| AWS | 0.9 | s3, ec2, lambda, sagemaker |
| GCP | 0.9 | google cloud, bigquery |
| Kubernetes | 0.8 | k8s |
| Docker | 0.7 | containers |
| Terraform | 0.6 | iac |

---

## Hiring Signal Scoring

| Signal Type | Points | Examples |
|-------------|--------|----------|
| Strong hiring language | +30 | "we're hiring", "now hiring", "open positions" |
| Active job listings | +40 | Multiple job titles detected |
| Has careers page | +20 | `/careers` or `/jobs` URL found |
| Funding mention | +40 | "series a/b/c", "raised $X" |
| Growth language | +30 | "growing team", "expanding" |
| Remote indicators | +20 | "remote-first", "distributed" |
| Contact available | +10 | careers@ email found |

---

## File Structure Reference

```
hidden-job-market/
├── config/                      # Configuration files
│   ├── config.yaml             # Main settings
│   ├── keywords.yaml           # Tech keywords + weights
│   ├── roles.yaml              # Target role patterns
│   └── blocklist.yaml          # Domains to skip
│
├── src/                         # Source code
│   ├── discovery/              # Layer 1: Dorking
│   │   ├── dork_engine.py      # Query generator
│   │   └── __init__.py
│   │
│   ├── extraction/             # Layer 2: Scraping
│   │   ├── scraper.py          # Main scraper
│   │   ├── robots_checker.py   # Compliance
│   │   ├── change_detector.py  # Monitor changes
│   │   └── __init__.py
│   │
│   ├── scoring/                # Layer 3: Scoring
│   │   ├── scorer.py           # Lead scorer
│   │   ├── formulas.py         # Documentation
│   │   └── __init__.py
│   │
│   └── utils/                  # Shared utilities
│       ├── database.py         # SQLite manager
│       ├── rate_limiter.py     # Request throttling
│       └── __init__.py
│
├── data/                        # Data storage
│   ├── raw/                    # Raw discoveries
│   ├── processed/              # Cleaned data
│   └── leads.db                # SQLite database
│
├── output/                      # Generated outputs
│   ├── reports/                # CSV exports
│   ├── scrape_results/         # Scraper output
│   └── alerts/                 # Change logs
│
├── docs/                        # Documentation
│   ├── DORK_REFERENCE.md       # Dork guide
│   ├── LEGAL_GUIDELINES.md     # Compliance
│   ├── WORKFLOW.md             # Pipeline docs
│   ├── SCHEMA.md               # Data schemas
│   └── TABLES.md               # This file
│
├── requirements.txt             # Dependencies
└── README.md                    # Project overview
```

---

## Command Quick Reference

| Task | Command |
|------|---------|
| Generate all dorks | `python src/discovery/dork_engine.py --all --format urls` |
| Generate careers dorks only | `python src/discovery/dork_engine.py -c careers --format urls` |
| Scrape single domain | `python src/extraction/scraper.py --domain example.com` |
| Scrape from file | `python src/extraction/scraper.py --input domains.txt` |
| Score leads | `python src/scoring/scorer.py --input profiles.csv` |
| View high priority | `python src/scoring/scorer.py --priority high` |
| Detect changes | `python src/extraction/change_detector.py --all-high-priority` |

---

## Rate Limiting Defaults

| Setting | Value | Purpose |
|---------|-------|---------|
| Min delay | 2 seconds | Minimum between requests |
| Max delay | 5 seconds | Maximum (with jitter) |
| Per-domain/hour | 20 requests | Prevent domain abuse |
| Backoff multiplier | 2x | Exponential on errors |
| Max backoff | 300 seconds | Cap on backoff time |

---

## Change Detection Types

| Type | Trigger | Action |
|------|---------|--------|
| `new_listing` | New job title appeared | High priority alert |
| `removed_listing` | Job title disappeared | Update records |
| `content_change` | Page hash changed | Re-scrape page |
| `new_signal` | New hiring/funding signal | Re-score lead |
| `score_change` | Score changed ≥10 points | Review lead |
