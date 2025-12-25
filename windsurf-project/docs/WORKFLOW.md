# System Workflow & Pipeline Documentation

## Text-Based Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DAILY WORKFLOW                                     │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────┐
    │   START     │
    └──────┬──────┘
           │
           ▼
┌──────────────────────┐     ┌─────────────────────────────────────────────┐
│  1. DISCOVERY PHASE  │     │  Input: config/config.yaml                  │
│  (Morning, ~15 min)  │     │  - Target roles                             │
│                      │     │  - Tech keywords                            │
│  python dork_engine  │     │  - Location preferences                     │
│  --all --format urls │     │                                             │
└──────────┬───────────┘     └─────────────────────────────────────────────┘
           │
           │ Generates: output/dork_urls.txt
           │ (50-100 Google search URLs)
           ▼
┌──────────────────────┐     ┌─────────────────────────────────────────────┐
│  2. MANUAL REVIEW    │     │  Actions:                                   │
│  (Browser, ~30 min)  │     │  - Open URLs in browser (with delays)       │
│                      │     │  - Scan results for relevant companies      │
│  Open dork URLs      │     │  - Copy promising domains to domains.txt    │
│  Review results      │     │  - Skip job boards, agencies, duplicates    │
└──────────┬───────────┘     └─────────────────────────────────────────────┘
           │
           │ Creates: data/raw/domains_{date}.txt
           │ (10-30 new domains per session)
           ▼
┌──────────────────────┐     ┌─────────────────────────────────────────────┐
│  3. EXTRACTION PHASE │     │  Automatic:                                 │
│  (Background, ~1hr)  │     │  - robots.txt compliance check              │
│                      │     │  - Rate-limited requests (2-5s delays)      │
│  python scraper.py   │     │  - Careers page discovery                   │
│  --input domains.txt │     │  - Data extraction (titles, tech, signals)  │
└──────────┬───────────┘     └─────────────────────────────────────────────┘
           │
           │ Outputs: 
           │ - output/scrape_results/profiles.csv
           │ - output/scrape_results/pages.csv
           │ - data/leads.db (SQLite)
           ▼
┌──────────────────────┐     ┌─────────────────────────────────────────────┐
│  4. SCORING PHASE    │     │  Scoring Components:                        │
│  (Instant)           │     │  - Role match (30%)                         │
│                      │     │  - Tech match (25%)                         │
│  python scorer.py    │     │  - Hiring signals (20%)                     │
│  --input profiles    │     │  - Company signals (15%)                    │
└──────────┬───────────┘     │  - Recency (10%)                            │
           │                 └─────────────────────────────────────────────┘
           │
           │ Outputs:
           │ - output/reports/scored_leads_{date}.csv
           │ - Terminal display of top leads
           ▼
┌──────────────────────┐     ┌─────────────────────────────────────────────┐
│  5. ACTION PHASE     │     │  For HIGH priority leads:                   │
│  (Manual, ongoing)   │     │  - Visit careers page                       │
│                      │     │  - Research company                         │
│  Review high-score   │     │  - Prepare tailored application             │
│  leads & take action │     │  - Track in personal CRM                    │
└──────────┬───────────┘     └─────────────────────────────────────────────┘
           │
           ▼
    ┌─────────────┐
    │    END      │
    │  (Repeat    │
    │   Daily)    │
    └─────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                        WEEKLY WORKFLOW                                       │
└─────────────────────────────────────────────────────────────────────────────┘

    Monday-Friday: Daily workflow above
    
    Saturday: 
    ┌──────────────────────┐
    │  CHANGE DETECTION    │
    │                      │
    │  python change_      │
    │  detector.py         │
    │  --domains high_     │
    │  priority.txt        │
    └──────────┬───────────┘
               │
               │ Detects:
               │ - New job listings
               │ - Removed listings
               │ - Content changes
               ▼
    ┌──────────────────────┐
    │  RE-SCORE CHANGED    │
    │  DOMAINS             │
    └──────────────────────┘
    
    Sunday:
    ┌──────────────────────┐
    │  CLEANUP & REVIEW    │
    │                      │
    │  - Archive old data  │
    │  - Update blocklist  │
    │  - Tune keywords     │
    │  - Review metrics    │
    └──────────────────────┘
```

---

## Pipeline Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FLOW DIAGRAM                                   │
└─────────────────────────────────────────────────────────────────────────────┘

CONFIG FILES                    DISCOVERY                      RAW DATA
─────────────                   ─────────                      ────────
config.yaml ──────┐
keywords.yaml ────┼──▶ dork_engine.py ──▶ dork_urls.txt ──▶ [Manual Review]
roles.yaml ───────┤                                               │
blocklist.yaml ───┘                                               │
                                                                  ▼
                                                          domains_{date}.txt
                                                                  │
                                                                  │
EXTRACTION                      PROCESSING                 STRUCTURED DATA
──────────                      ──────────                 ───────────────
                                    │
domains.txt ──▶ scraper.py ─────────┼──▶ pages.csv
                    │               │         │
                    │               │         ▼
                    │               └──▶ profiles.csv
                    │                         │
                    ▼                         │
              robots.txt ◀── [Compliance]     │
                                              │
                                              ▼
SCORING                         DATABASE                   REPORTS
───────                         ────────                   ───────
                                    │
profiles.csv ──▶ scorer.py ─────────┼──▶ leads.db (SQLite)
                    │               │         │
                    │               │         ▼
                    │               └──▶ scored_leads.csv
                    │                         │
                    ▼                         │
              [Terminal Display]              │
                                              ▼
                                    ┌─────────────────┐
                                    │  HIGH PRIORITY  │
                                    │     LEADS       │
                                    │  (Action List)  │
                                    └─────────────────┘
```

---

## Input/Output Tables

### Discovery Layer

| Input | Tool | Output | Format |
|-------|------|--------|--------|
| `config/config.yaml` | `dork_engine.py` | Dork queries | Text |
| `config/keywords.yaml` | `dork_engine.py` | Google URLs | `.txt` |
| `config/roles.yaml` | `dork_engine.py` | Query CSV | `.csv` |
| `config/blocklist.yaml` | `dork_engine.py` | - | - |

### Extraction Layer

| Input | Tool | Output | Format |
|-------|------|--------|--------|
| `domains.txt` | `scraper.py` | `pages.csv` | CSV |
| `config.yaml` | `scraper.py` | `profiles.csv` | CSV |
| `keywords.yaml` | `robots_checker.py` | `leads.db` | SQLite |
| - | `rate_limiter.py` | - | - |

### Scoring Layer

| Input | Tool | Output | Format |
|-------|------|--------|--------|
| `profiles.csv` | `scorer.py` | `scored_leads.csv` | CSV |
| `config.yaml` | `scorer.py` | Terminal table | Display |
| `keywords.yaml` | `scorer.py` | `leads.db` updates | SQLite |
| `roles.yaml` | `scorer.py` | - | - |

---

## File Naming Conventions

```
data/
├── raw/
│   ├── domains_2024-01-15.txt      # Daily discovered domains
│   ├── domains_2024-01-16.txt
│   └── discoveries_2024-01-15.csv  # Dork results with metadata
│
├── processed/
│   └── merged_domains.txt          # Deduplicated master list
│
└── leads.db                        # SQLite database

output/
├── reports/
│   ├── scored_leads_2024-01-15.csv # Daily scored output
│   ├── scored_leads_2024-01-16.csv
│   └── weekly_summary_2024-W03.csv # Weekly aggregates
│
├── scrape_results/
│   ├── pages.csv                   # All scraped pages
│   └── profiles.csv                # Company profiles
│
└── alerts/
    └── changes_2024-01-15.json     # Change detection log
```

---

## Quick Reference Commands

### Daily Commands

```bash
# 1. Generate dork URLs
python src/discovery/dork_engine.py --all --format urls -o output/dork_urls.txt

# 2. After manual review, scrape domains
python src/extraction/scraper.py --input data/raw/domains_$(date +%Y-%m-%d).txt

# 3. Score leads
python src/scoring/scorer.py --input output/scrape_results/profiles.csv

# 4. View high-priority only
python src/scoring/scorer.py --priority high --limit 20
```

### Utility Commands

```bash
# Export specific category dorks
python src/discovery/dork_engine.py -c careers -c hiring_signals --format csv

# Scrape single domain
python src/extraction/scraper.py --domain example.com

# Check database stats
python -c "from src.utils.database import LeadDatabase; print(LeadDatabase().get_stats())"
```

---

## Automation (Optional)

### Cron Schedule (Linux/Mac)

```cron
# Generate dorks at 8am daily
0 8 * * * cd /path/to/project && python src/discovery/dork_engine.py --all --format urls

# Run scoring at 6pm daily (after manual scraping)
0 18 * * * cd /path/to/project && python src/scoring/scorer.py --export csv

# Weekly change detection on Saturday
0 10 * * 6 cd /path/to/project && python src/extraction/change_detector.py
```

### Task Scheduler (Windows)

Create scheduled tasks for the same commands using Windows Task Scheduler.
