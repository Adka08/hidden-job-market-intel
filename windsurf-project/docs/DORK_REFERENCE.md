# Google Dorking Reference Guide

## Overview

Google dorks are advanced search operators that help discover specific content. This guide provides categorized dorks optimized for uncovering the hidden job market.

---

## 1️⃣ CAREERS PAGE DORKS

### Purpose
Find company career pages directly, bypassing job boards.

### Dorks

| Dork | Why It Works | When to Use |
|------|--------------|-------------|
| `site:*.com inurl:careers` | Targets `/careers` URL paths common in company sites | Daily discovery |
| `site:*.com inurl:jobs -site:linkedin.com -site:indeed.com` | Finds `/jobs` pages while excluding boards | Daily discovery |
| `intitle:"careers" "join our team"` | Matches career page titles with hiring language | Broad discovery |
| `inurl:careers "open positions" python` | Combines careers URL with tech keyword | Tech-specific search |
| `site:*.io inurl:careers` | Targets startups (often use .io domains) | Startup focus |
| `"careers at" "data engineer" -linkedin -indeed` | Natural language career pages | Role-specific |
| `inurl:/careers/ "apply now"` | Active hiring pages with application CTAs | High-intent leads |
| `"work with us" OR "join us" inurl:about` | About pages with hiring sections | Smaller companies |

### Pro Tips
- `.io`, `.co`, `.ai` TLDs often indicate startups
- Combine with location: `"san francisco" OR "remote"`
- Add `-staffing -recruitment -agency` to filter noise

---

## 2️⃣ HIRING SIGNAL DORKS

### Purpose
Detect companies actively hiring even without formal job posts.

### Dorks

| Dork | Why It Works | When to Use |
|------|--------------|-------------|
| `"we're hiring" "engineer" site:*.com` | Direct hiring announcements | High-intent discovery |
| `"growing team" "data" -jobs -careers` | Growth language without formal pages | Early-stage companies |
| `"join our engineering team" python` | Team-specific hiring with tech | Targeted search |
| `"now hiring" "remote" "backend"` | Active + remote + role | Remote-specific |
| `"expanding our" "data team"` | Expansion language | Growth companies |
| `"looking for" "senior engineer" site:*.com` | Informal hiring posts | Blog/about pages |
| `"come build with us" OR "help us build"` | Startup hiring language | Early-stage |
| `"hiring for" "multiple positions"` | Bulk hiring signals | Scaling companies |

### Pro Tips
- These often appear on blog posts, about pages, or team pages
- Check page dates—recent posts = active hiring
- Combine with funding signals for hot leads

---

## 3️⃣ TECH STACK DORKS

### Purpose
Find companies using your target technologies.

### Dorks

| Dork | Why It Works | When to Use |
|------|--------------|-------------|
| `"we use" "python" "spark" site:*.com` | Tech stack disclosure | Stack matching |
| `"built with" "kubernetes" "aws"` | Infrastructure mentions | DevOps/Platform roles |
| `"our stack" python OR golang` | Explicit stack pages | Tech-focused companies |
| `"tech stack" "pytorch" OR "tensorflow"` | ML stack mentions | ML/AI roles |
| `inurl:engineering "airflow" "data pipeline"` | Engineering blogs with tech | Data engineering |
| `"powered by" "databricks" OR "snowflake"` | Data platform mentions | Data roles |
| `site:*.ai "llm" OR "gpt" "team"` | AI companies with LLM work | AI/ML roles |
| `"microservices" "kafka" careers` | Architecture + hiring | Backend roles |

### Pro Tips
- Engineering blogs often reveal stack before job posts
- GitHub org pages can indicate tech preferences
- Combine multiple techs: `python AND (spark OR airflow)`

---

## 4️⃣ GROWTH & FUNDING DORKS

### Purpose
Find companies with recent funding (likely to hire).

### Dorks

| Dork | Why It Works | When to Use |
|------|--------------|-------------|
| `"series a" "hiring" 2024` | Recent funding + hiring | Post-funding surge |
| `"raised" "$" "million" "team" site:*.com` | Funding announcements | Growth companies |
| `"backed by" "sequoia" OR "a]6z" careers` | VC-backed companies | Well-funded startups |
| `"y combinator" "batch" "hiring"` | YC companies | Startup ecosystem |
| `"seed round" "growing" engineer` | Early-stage funded | Early opportunities |
| `"series b" "scaling" "data"` | Growth-stage scaling | Scaling teams |
| `site:techcrunch.com "raises" "hiring"` | News + hiring signals | Recent funding |
| `"unicorn" "engineering team" careers` | High-value startups | Top-tier startups |

### Pro Tips
- Funding announcements often precede job posts by 2-4 weeks
- Series A/B companies often have urgent hiring needs
- YC companies batch-hire after demo day

---

## 5️⃣ REMOTE-SPECIFIC DORKS

### Purpose
Find remote-friendly companies.

### Dorks

| Dork | Why It Works | When to Use |
|------|--------------|-------------|
| `"remote-first" "engineer" careers` | Remote-first culture | Remote priority |
| `"fully remote" "data" "hiring"` | 100% remote positions | Remote-only search |
| `"distributed team" "python" careers` | Distributed companies | Remote culture |
| `"work from anywhere" engineer` | Location-flexible | Global remote |
| `"async" "remote" "engineering team"` | Async-first remote | Time-zone flexible |
| `inurl:careers "remote" -"hybrid" -"on-site"` | Remote excluding hybrid | Pure remote |
| `"timezone" "flexible" engineer hiring` | TZ-flexible companies | International |

---

## 6️⃣ COMPANY SIZE DORKS

### Purpose
Target companies by stage/size.

### Dorks

| Dork | Why It Works | When to Use |
|------|--------------|-------------|
| `"small team" "engineer" "hiring"` | Early-stage startups | Startup preference |
| `"startup" "founding engineer"` | Founding roles | Early equity |
| `"enterprise" "platform team" careers` | Large company teams | Enterprise roles |
| `"scale-up" "data team" hiring` | Growth-stage | Scaling companies |
| `employees:50-200 site:*.com careers` | Mid-size companies | Goldilocks zone |

---

## DUPLICATE & NOISE REDUCTION

### Exclusion Operators

```
# Always exclude job boards
-site:linkedin.com -site:indeed.com -site:glassdoor.com -site:ziprecruiter.com

# Exclude staffing agencies
-staffing -recruitment -"recruitment agency" -"staffing agency"

# Exclude outdated results
after:2024-01-01

# Exclude specific content types
-filetype:pdf -filetype:doc
```

### Domain Quality Filters

```
# Prefer company TLDs
site:*.com OR site:*.io OR site:*.co OR site:*.ai

# Exclude low-quality TLDs
-site:*.info -site:*.biz -site:*.xyz

# Exclude government/education
-site:*.gov -site:*.edu
```

### Deduplication Strategy

1. **Extract root domain** from each result
2. **Normalize** (remove www, trailing slashes)
3. **Store in set** to prevent re-processing
4. **Check against blocklist** before adding

---

## QUERY ROTATION STRATEGY

To avoid rate limiting and maximize coverage:

### Daily Rotation Schedule

| Day | Focus | Example Query |
|-----|-------|---------------|
| Mon | Careers pages | `inurl:careers "data engineer" remote` |
| Tue | Hiring signals | `"we're hiring" "backend" python` |
| Wed | Tech stack | `"our stack" spark airflow careers` |
| Thu | Funding/Growth | `"series b" "hiring" "data team"` |
| Fri | Remote-specific | `"remote-first" "ml engineer"` |
| Sat | Review & score | Process week's discoveries |
| Sun | Change detection | Re-check high-score leads |

### Rate Limiting Best Practices

- **30-60 seconds** between queries
- **Max 50 queries** per session
- **Rotate IP** if possible (VPN)
- **Use different browsers** or incognito
- **Respect Google's ToS**

---

## COMBINING DORKS

### High-Precision Compound Queries

```
# ML Engineer at funded startup, remote
"series a" OR "series b" "ml engineer" OR "machine learning" "remote" -linkedin -indeed

# Data Engineer with specific stack
inurl:careers "data engineer" "spark" OR "airflow" "python" remote

# Backend at AI company
site:*.ai inurl:careers "backend" OR "platform" "python" "hiring"

# Senior role at growing company
"senior" "engineer" "growing team" "python" site:*.com -staffing
```

---

## OUTPUT FORMAT

Each dork execution should produce:

```csv
query,result_url,domain,title,snippet,discovered_at
"inurl:careers python",https://acme.com/careers,acme.com,"Careers | Acme","Join our data team...",2024-01-15T10:30:00Z
```

Store in `data/raw/discoveries_{date}.csv`
