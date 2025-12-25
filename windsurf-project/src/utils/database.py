"""
SQLite Database Manager for Lead Storage

Handles persistent storage of:
- Discovered domains
- Scraped pages
- Company profiles
- Lead scores
- Change detection history
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from contextlib import contextmanager


class LeadDatabase:
    """
    SQLite database for storing job market intelligence data.
    
    Tables:
    - domains: Discovered domains from dorking
    - pages: Individual scraped pages
    - companies: Aggregated company profiles
    - scores: Lead scores with history
    - changes: Change detection log
    """
    
    SCHEMA = """
    -- Discovered domains from Google dorking
    CREATE TABLE IF NOT EXISTS domains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT UNIQUE NOT NULL,
        source_query TEXT,
        category TEXT,
        discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',  -- pending, scraped, blocked, error
        notes TEXT
    );
    
    -- Individual scraped pages
    CREATE TABLE IF NOT EXISTS pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        domain TEXT NOT NULL,
        title TEXT,
        page_type TEXT,
        content_hash TEXT,
        status_code INTEGER,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Extracted data (JSON arrays)
        job_titles TEXT,
        tech_keywords TEXT,
        hiring_signals TEXT,
        remote_indicators TEXT,
        contact_emails TEXT,
        
        -- Flags
        has_apply_button BOOLEAN DEFAULT FALSE,
        has_job_listings BOOLEAN DEFAULT FALSE,
        
        FOREIGN KEY (domain) REFERENCES domains(domain)
    );
    
    -- Aggregated company profiles
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT UNIQUE NOT NULL,
        name TEXT,
        careers_url TEXT,
        
        -- Aggregated data (JSON arrays)
        all_job_titles TEXT,
        all_tech_keywords TEXT,
        all_hiring_signals TEXT,
        all_remote_indicators TEXT,
        all_contact_emails TEXT,
        
        -- Metadata
        pages_scraped INTEGER DEFAULT 0,
        has_active_listings BOOLEAN DEFAULT FALSE,
        first_seen TIMESTAMP,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (domain) REFERENCES domains(domain)
    );
    
    -- Lead scores with history
    CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        total_score REAL,
        priority TEXT,
        
        -- Component scores
        role_score REAL,
        tech_score REAL,
        hiring_score REAL,
        company_score REAL,
        recency_score REAL,
        
        -- Match details (JSON)
        matched_roles TEXT,
        matched_techs TEXT,
        matched_signals TEXT,
        
        scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (domain) REFERENCES domains(domain)
    );
    
    -- Change detection log
    CREATE TABLE IF NOT EXISTS changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        url TEXT,
        change_type TEXT,  -- new_listing, removed_listing, content_change, score_change
        old_value TEXT,
        new_value TEXT,
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (domain) REFERENCES domains(domain)
    );
    
    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_domains_status ON domains(status);
    CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain);
    CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
    CREATE INDEX IF NOT EXISTS idx_scores_domain ON scores(domain);
    CREATE INDEX IF NOT EXISTS idx_scores_priority ON scores(priority);
    CREATE INDEX IF NOT EXISTS idx_changes_domain ON changes(domain);
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / 'data' / 'leads.db'
        
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    # =========================================================================
    # DOMAIN OPERATIONS
    # =========================================================================
    
    def add_domain(
        self,
        domain: str,
        source_query: str = "",
        category: str = ""
    ) -> bool:
        """Add a discovered domain. Returns True if new, False if exists."""
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """INSERT INTO domains (domain, source_query, category)
                       VALUES (?, ?, ?)""",
                    (domain, source_query, category)
                )
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_pending_domains(self, limit: int = 100) -> List[Dict]:
        """Get domains pending scraping."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM domains WHERE status = 'pending'
                   ORDER BY discovered_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def update_domain_status(self, domain: str, status: str, notes: str = ""):
        """Update domain status."""
        with self._get_connection() as conn:
            conn.execute(
                """UPDATE domains SET status = ?, notes = ?
                   WHERE domain = ?""",
                (status, notes, domain)
            )
    
    # =========================================================================
    # PAGE OPERATIONS
    # =========================================================================
    
    def add_page(self, page_data: Dict) -> int:
        """Add a scraped page. Returns page ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT OR REPLACE INTO pages 
                   (url, domain, title, page_type, content_hash, status_code,
                    job_titles, tech_keywords, hiring_signals, remote_indicators,
                    contact_emails, has_apply_button, has_job_listings, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    page_data['url'],
                    page_data['domain'],
                    page_data.get('title', ''),
                    page_data.get('page_type', 'unknown'),
                    page_data.get('content_hash', ''),
                    page_data.get('status_code', 0),
                    json.dumps(page_data.get('job_titles', [])),
                    json.dumps(page_data.get('tech_keywords', [])),
                    json.dumps(page_data.get('hiring_signals', [])),
                    json.dumps(page_data.get('remote_indicators', [])),
                    json.dumps(page_data.get('contact_emails', [])),
                    page_data.get('has_apply_button', False),
                    page_data.get('has_job_listings', False),
                    datetime.now().isoformat()
                )
            )
            return cursor.lastrowid
    
    def get_page_by_url(self, url: str) -> Optional[Dict]:
        """Get page by URL."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM pages WHERE url = ?", (url,)
            ).fetchone()
            if row:
                data = dict(row)
                # Parse JSON fields
                for field in ['job_titles', 'tech_keywords', 'hiring_signals',
                              'remote_indicators', 'contact_emails']:
                    if data.get(field):
                        data[field] = json.loads(data[field])
                return data
            return None
    
    def get_content_hash(self, url: str) -> Optional[str]:
        """Get content hash for change detection."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT content_hash FROM pages WHERE url = ?", (url,)
            ).fetchone()
            return row['content_hash'] if row else None
    
    # =========================================================================
    # COMPANY OPERATIONS
    # =========================================================================
    
    def upsert_company(self, company_data: Dict):
        """Insert or update company profile."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO companies 
                   (domain, name, careers_url, all_job_titles, all_tech_keywords,
                    all_hiring_signals, all_remote_indicators, all_contact_emails,
                    pages_scraped, has_active_listings, first_seen, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(domain) DO UPDATE SET
                    name = excluded.name,
                    careers_url = COALESCE(excluded.careers_url, careers_url),
                    all_job_titles = excluded.all_job_titles,
                    all_tech_keywords = excluded.all_tech_keywords,
                    all_hiring_signals = excluded.all_hiring_signals,
                    all_remote_indicators = excluded.all_remote_indicators,
                    all_contact_emails = excluded.all_contact_emails,
                    pages_scraped = excluded.pages_scraped,
                    has_active_listings = excluded.has_active_listings,
                    last_updated = excluded.last_updated""",
                (
                    company_data['domain'],
                    company_data.get('name', ''),
                    company_data.get('careers_url', ''),
                    json.dumps(list(company_data.get('all_job_titles', []))),
                    json.dumps(list(company_data.get('all_tech_keywords', []))),
                    json.dumps(list(company_data.get('all_hiring_signals', []))),
                    json.dumps(list(company_data.get('all_remote_indicators', []))),
                    json.dumps(list(company_data.get('all_contact_emails', []))),
                    company_data.get('pages_scraped', 0),
                    company_data.get('has_active_listings', False),
                    company_data.get('first_seen', datetime.now()).isoformat()
                        if company_data.get('first_seen') else datetime.now().isoformat(),
                    datetime.now().isoformat()
                )
            )
    
    def get_company(self, domain: str) -> Optional[Dict]:
        """Get company by domain."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE domain = ?", (domain,)
            ).fetchone()
            if row:
                data = dict(row)
                # Parse JSON fields
                for field in ['all_job_titles', 'all_tech_keywords', 'all_hiring_signals',
                              'all_remote_indicators', 'all_contact_emails']:
                    if data.get(field):
                        data[field] = json.loads(data[field])
                return data
            return None
    
    def get_all_companies(self) -> List[Dict]:
        """Get all companies."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM companies ORDER BY last_updated DESC"
            ).fetchall()
            companies = []
            for row in rows:
                data = dict(row)
                for field in ['all_job_titles', 'all_tech_keywords', 'all_hiring_signals',
                              'all_remote_indicators', 'all_contact_emails']:
                    if data.get(field):
                        data[field] = json.loads(data[field])
                companies.append(data)
            return companies
    
    # =========================================================================
    # SCORE OPERATIONS
    # =========================================================================
    
    def add_score(self, score_data: Dict):
        """Add a lead score."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO scores 
                   (domain, total_score, priority, role_score, tech_score,
                    hiring_score, company_score, recency_score,
                    matched_roles, matched_techs, matched_signals)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    score_data['domain'],
                    score_data['total_score'],
                    score_data['priority'],
                    score_data.get('role_score', 0),
                    score_data.get('tech_score', 0),
                    score_data.get('hiring_score', 0),
                    score_data.get('company_score', 0),
                    score_data.get('recency_score', 0),
                    json.dumps(score_data.get('matched_roles', [])),
                    json.dumps(score_data.get('matched_techs', [])),
                    json.dumps(score_data.get('matched_signals', []))
                )
            )
    
    def get_latest_scores(self, priority: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get latest scores, optionally filtered by priority."""
        with self._get_connection() as conn:
            if priority:
                rows = conn.execute(
                    """SELECT * FROM scores WHERE priority = ?
                       ORDER BY scored_at DESC LIMIT ?""",
                    (priority, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM scores
                       ORDER BY total_score DESC, scored_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
            
            scores = []
            for row in rows:
                data = dict(row)
                for field in ['matched_roles', 'matched_techs', 'matched_signals']:
                    if data.get(field):
                        data[field] = json.loads(data[field])
                scores.append(data)
            return scores
    
    def get_score_history(self, domain: str) -> List[Dict]:
        """Get score history for a domain."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM scores WHERE domain = ?
                   ORDER BY scored_at DESC""",
                (domain,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    # =========================================================================
    # CHANGE DETECTION
    # =========================================================================
    
    def log_change(
        self,
        domain: str,
        change_type: str,
        old_value: Any = None,
        new_value: Any = None,
        url: str = ""
    ):
        """Log a detected change."""
        with self._get_connection() as conn:
            conn.execute(
                """INSERT INTO changes (domain, url, change_type, old_value, new_value)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    domain,
                    url,
                    change_type,
                    json.dumps(old_value) if old_value else None,
                    json.dumps(new_value) if new_value else None
                )
            )
    
    def get_recent_changes(self, days: int = 7) -> List[Dict]:
        """Get changes from the last N days."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM changes 
                   WHERE detected_at >= datetime('now', ?)
                   ORDER BY detected_at DESC""",
                (f'-{days} days',)
            ).fetchall()
            return [dict(row) for row in rows]
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            stats = {}
            
            # Domain counts by status
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM domains GROUP BY status"
            ).fetchall()
            stats['domains_by_status'] = {row['status']: row['count'] for row in rows}
            
            # Total pages
            row = conn.execute("SELECT COUNT(*) as count FROM pages").fetchone()
            stats['total_pages'] = row['count']
            
            # Total companies
            row = conn.execute("SELECT COUNT(*) as count FROM companies").fetchone()
            stats['total_companies'] = row['count']
            
            # Score distribution
            rows = conn.execute(
                """SELECT priority, COUNT(*) as count 
                   FROM (SELECT domain, priority FROM scores 
                         GROUP BY domain HAVING MAX(scored_at))
                   GROUP BY priority"""
            ).fetchall()
            stats['scores_by_priority'] = {row['priority']: row['count'] for row in rows}
            
            # Recent changes
            row = conn.execute(
                """SELECT COUNT(*) as count FROM changes 
                   WHERE detected_at >= datetime('now', '-7 days')"""
            ).fetchone()
            stats['changes_last_7_days'] = row['count']
            
            return stats
