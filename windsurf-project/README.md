# Hidden Job Market Intelligence System

A high-efficiency, legally compliant system for discovering hiring signals before roles appear on job boards.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HIDDEN JOB MARKET SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    1️⃣ DISCOVERY LAYER                                │   │
│  │                   (Google Dorking Engine)                           │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ Careers Page │  │ Hiring Signal│  │ Tech Stack   │              │   │
│  │  │    Dorks     │  │    Dorks     │  │    Dorks     │              │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │   │
│  │         │                 │                 │                       │   │
│  │         └─────────────────┼─────────────────┘                       │   │
│  │                           ▼                                         │   │
│  │              ┌────────────────────────┐                             │   │
│  │              │   Domain Deduplication │                             │   │
│  │              │   & Quality Filtering  │                             │   │
│  │              └───────────┬────────────┘                             │   │
│  └──────────────────────────┼──────────────────────────────────────────┘   │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    2️⃣ EXTRACTION LAYER                               │   │
│  │                  (Scraping + Intelligence)                          │   │
│  │                                                                     │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │                    robots.txt Check                          │  │   │
│  │  └──────────────────────────┬───────────────────────────────────┘  │   │
│  │                             ▼                                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ Careers Page │  │ Role Title   │  │ Tech Keyword │              │   │
│  │  │  Detection   │  │  Extraction  │  │  Extraction  │              │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │   │
│  │         │                 │                 │                       │   │
│  │         └─────────────────┼─────────────────┘                       │   │
│  │                           ▼                                         │   │
│  │              ┌────────────────────────┐                             │   │
│  │              │    SCORING ENGINE      │                             │   │
│  │              │  (Lead Qualification)  │                             │   │
│  │              └───────────┬────────────┘                             │   │
│  └──────────────────────────┼──────────────────────────────────────────┘   │
│                             ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       3️⃣ OUTPUT LAYER                                │   │
│  │                                                                     │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │  SQLite DB   │  │  CSV Export  │  │    Alerts    │              │   │
│  │  │  (Primary)   │  │  (Reports)   │  │  (Optional)  │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure your preferences
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your keywords, roles, locations

# 3. Run discovery (generates dork URLs)
python src/discovery/dork_engine.py

# 4. Run extraction on discovered domains
python src/extraction/scraper.py

# 5. View scored leads
python src/scoring/scorer.py --export csv
```

## Project Structure

```
hidden-job-market/
├── config/
│   ├── config.yaml           # Main configuration
│   ├── keywords.yaml         # Tech keywords & weights
│   ├── roles.yaml            # Target role patterns
│   └── blocklist.yaml        # Domains to skip
├── src/
│   ├── discovery/
│   │   ├── dork_engine.py    # Google dork generator
│   │   └── dorks/            # Categorized dork templates
│   ├── extraction/
│   │   ├── scraper.py        # Main scraper
│   │   ├── robots_checker.py # robots.txt compliance
│   │   └── detectors/        # Page type detectors
│   ├── scoring/
│   │   ├── scorer.py         # Lead scoring engine
│   │   └── formulas.py       # Scoring formulas
│   └── utils/
│       ├── deduplicator.py   # Domain deduplication
│       └── rate_limiter.py   # Request throttling
├── data/
│   ├── raw/                  # Raw scraped data
│   ├── processed/            # Normalized data
│   └── leads.db              # SQLite database
├── output/
│   ├── reports/              # CSV exports
│   └── alerts/               # Change detection logs
└── docs/
    ├── DORK_REFERENCE.md     # Dork documentation
    └── LEGAL_GUIDELINES.md   # Compliance notes
```

## Legal & Ethical Compliance

- ✅ Respects robots.txt
- ✅ Rate-limited requests (2-5 sec delays)
- ✅ Public data only (no login bypass)
- ✅ No mass emailing or spam
- ✅ User-agent identification

## License

MIT - For personal use in job discovery only.
