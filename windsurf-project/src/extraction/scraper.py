"""
Web Scraper for Hidden Job Market Intelligence

Three-tier architecture:
- MVP: Basic HTML parsing, careers page detection
- Beta: JavaScript rendering, structured data extraction
- Advanced: ML-based content classification, change detection

Usage:
    python scraper.py --input domains.txt --output results.csv
    python scraper.py --url https://example.com/careers
"""

import os
import sys
import re
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse, urljoin
import csv

import requests
from bs4 import BeautifulSoup
import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.rate_limiter import RateLimiter, RateLimitConfig
from src.extraction.robots_checker import RobotsChecker

from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table
import click

console = Console()


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ScrapedPage:
    """Represents a scraped web page."""
    url: str
    domain: str
    title: str
    content_hash: str
    scraped_at: datetime
    status_code: int
    page_type: str = "unknown"  # careers, jobs, about, team, engineering, other
    
    # Extracted data
    job_titles: List[str] = field(default_factory=list)
    tech_keywords: List[str] = field(default_factory=list)
    hiring_signals: List[str] = field(default_factory=list)
    remote_indicators: List[str] = field(default_factory=list)
    contact_emails: List[str] = field(default_factory=list)
    
    # Metadata
    has_apply_button: bool = False
    has_job_listings: bool = False
    last_modified: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            **asdict(self),
            'scraped_at': self.scraped_at.isoformat(),
            'job_titles': json.dumps(self.job_titles),
            'tech_keywords': json.dumps(self.tech_keywords),
            'hiring_signals': json.dumps(self.hiring_signals),
            'remote_indicators': json.dumps(self.remote_indicators),
            'contact_emails': json.dumps(self.contact_emails)
        }


@dataclass
class CompanyProfile:
    """Aggregated profile for a company from multiple pages."""
    domain: str
    name: str = ""
    careers_url: Optional[str] = None
    
    # Aggregated from all pages
    all_job_titles: Set[str] = field(default_factory=set)
    all_tech_keywords: Set[str] = field(default_factory=set)
    all_hiring_signals: Set[str] = field(default_factory=set)
    all_remote_indicators: Set[str] = field(default_factory=set)
    all_contact_emails: Set[str] = field(default_factory=set)
    
    # Scoring inputs
    pages_scraped: int = 0
    has_active_listings: bool = False
    
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    
    def merge_page(self, page: ScrapedPage):
        """Merge data from a scraped page into the profile."""
        self.all_job_titles.update(page.job_titles)
        self.all_tech_keywords.update(page.tech_keywords)
        self.all_hiring_signals.update(page.hiring_signals)
        self.all_remote_indicators.update(page.remote_indicators)
        self.all_contact_emails.update(page.contact_emails)
        
        if page.page_type == 'careers' and not self.careers_url:
            self.careers_url = page.url
        
        if page.has_job_listings:
            self.has_active_listings = True
        
        self.pages_scraped += 1
        self.last_updated = datetime.now()
        
        if not self.first_seen:
            self.first_seen = datetime.now()


# =============================================================================
# DETECTORS
# =============================================================================

class PageTypeDetector:
    """Detects the type of page based on URL and content."""
    
    CAREERS_URL_PATTERNS = [
        r'/careers?/?',
        r'/jobs?/?',
        r'/work-with-us/?',
        r'/join-us/?',
        r'/opportunities/?',
        r'/openings/?',
        r'/positions/?',
        r'/hiring/?',
        r'/team/?.*jobs',
    ]
    
    CAREERS_CONTENT_PATTERNS = [
        r'open\s+positions?',
        r'current\s+openings?',
        r'job\s+openings?',
        r'career\s+opportunities',
        r'we\'?re\s+hiring',
        r'join\s+our\s+team',
        r'apply\s+now',
        r'view\s+all\s+jobs',
    ]
    
    @classmethod
    def detect(cls, url: str, soup: BeautifulSoup) -> str:
        """Detect page type from URL and content."""
        url_lower = url.lower()
        
        # Check URL patterns
        for pattern in cls.CAREERS_URL_PATTERNS:
            if re.search(pattern, url_lower):
                return 'careers'
        
        if '/about' in url_lower:
            return 'about'
        if '/team' in url_lower:
            return 'team'
        if '/engineering' in url_lower or '/blog' in url_lower:
            return 'engineering'
        
        # Check content patterns
        text = soup.get_text().lower()
        careers_score = 0
        
        for pattern in cls.CAREERS_CONTENT_PATTERNS:
            if re.search(pattern, text):
                careers_score += 1
        
        if careers_score >= 2:
            return 'careers'
        
        return 'other'


class TechKeywordExtractor:
    """Extracts technology keywords from page content."""
    
    def __init__(self, keywords_path: Optional[Path] = None):
        self.keywords = self._load_keywords(keywords_path)
    
    def _load_keywords(self, path: Optional[Path]) -> Dict[str, float]:
        """Load keywords and weights from config."""
        if path is None:
            path = PROJECT_ROOT / 'config' / 'keywords.yaml'
        
        keywords = {}
        
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                
                for category in ['languages', 'data_ml', 'infrastructure', 'databases']:
                    if category in data:
                        for keyword, info in data[category].items():
                            keywords[keyword.lower()] = info.get('weight', 0.5)
                            # Add aliases
                            for alias in info.get('aliases', []):
                                keywords[alias.lower()] = info.get('weight', 0.5)
        
        # Fallback defaults
        if not keywords:
            keywords = {
                'python': 1.0, 'java': 0.7, 'go': 0.8, 'rust': 0.6,
                'sql': 1.0, 'spark': 1.0, 'airflow': 1.0, 'kafka': 0.9,
                'kubernetes': 0.8, 'docker': 0.7, 'aws': 0.9, 'gcp': 0.9,
                'pytorch': 1.0, 'tensorflow': 0.9, 'mlflow': 0.9,
                'databricks': 1.0, 'snowflake': 0.9, 'dbt': 0.9
            }
        
        return keywords
    
    def extract(self, text: str) -> List[Tuple[str, float]]:
        """Extract tech keywords with their weights."""
        text_lower = text.lower()
        found = []
        
        for keyword, weight in self.keywords.items():
            # Word boundary matching
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                found.append((keyword, weight))
        
        # Sort by weight descending
        return sorted(found, key=lambda x: x[1], reverse=True)


class JobTitleExtractor:
    """Extracts job titles from page content."""
    
    TITLE_PATTERNS = [
        # Common job listing patterns
        r'<h[1-4][^>]*>([^<]*(?:engineer|developer|scientist|analyst|architect)[^<]*)</h[1-4]>',
        r'<a[^>]*>([^<]*(?:engineer|developer|scientist|analyst|architect)[^<]*)</a>',
        r'<li[^>]*>([^<]*(?:engineer|developer|scientist|analyst|architect)[^<]*)</li>',
        # Structured data
        r'"title"\s*:\s*"([^"]*(?:engineer|developer|scientist|analyst)[^"]*)"',
        r'"jobTitle"\s*:\s*"([^"]*)"',
    ]
    
    SENIORITY_PATTERNS = [
        r'\b(senior|sr\.?|staff|principal|lead|junior|jr\.?|mid[- ]?level)\b'
    ]
    
    @classmethod
    def extract(cls, html: str, soup: BeautifulSoup) -> List[str]:
        """Extract job titles from HTML."""
        titles = set()
        html_lower = html.lower()
        
        for pattern in cls.TITLE_PATTERNS:
            matches = re.findall(pattern, html_lower, re.IGNORECASE)
            for match in matches:
                # Clean and validate
                title = match.strip()
                if 10 < len(title) < 100:  # Reasonable title length
                    titles.add(title.title())
        
        # Also check structured data (JSON-LD)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get('@type') == 'JobPosting':
                        title = data.get('title', '')
                        if title:
                            titles.add(title)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'JobPosting':
                            title = item.get('title', '')
                            if title:
                                titles.add(title)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return list(titles)


class HiringSignalExtractor:
    """Extracts hiring signals from page content."""
    
    STRONG_SIGNALS = [
        r"we'?re\s+hiring",
        r"we\s+are\s+hiring",
        r"join\s+our\s+team",
        r"now\s+hiring",
        r"open\s+positions?",
        r"current\s+openings?",
        r"career\s+opportunities",
        r"come\s+work\s+with\s+us",
        r"growing\s+(?:our\s+)?team",
        r"expanding\s+(?:our\s+)?team",
    ]
    
    FUNDING_SIGNALS = [
        r"series\s+[a-d]",
        r"raised\s+\$?\d+",
        r"backed\s+by",
        r"y\s*combinator",
        r"yc\s+\w+\s+\d{4}",
    ]
    
    @classmethod
    def extract(cls, text: str) -> List[str]:
        """Extract hiring signals from text."""
        text_lower = text.lower()
        signals = []
        
        for pattern in cls.STRONG_SIGNALS:
            if re.search(pattern, text_lower):
                # Clean pattern for display (remove regex syntax)
                clean_pattern = pattern.replace(r'\s+', ' ').replace(r"'?", '').replace('\\', '')
                signals.append(f"hiring:{clean_pattern}")
        
        for pattern in cls.FUNDING_SIGNALS:
            match = re.search(pattern, text_lower)
            if match:
                signals.append(f"funding:{match.group()}")
        
        return signals


class RemoteIndicatorExtractor:
    """Extracts remote work indicators."""
    
    POSITIVE_PATTERNS = [
        r'\bremote\b',
        r'\bremote[- ]first\b',
        r'\bfully\s+remote\b',
        r'\bwork\s+from\s+(?:home|anywhere)\b',
        r'\bdistributed\s+team\b',
        r'\bremote[- ]friendly\b',
    ]
    
    HYBRID_PATTERNS = [
        r'\bhybrid\b',
        r'\bflexible\s+(?:work|location)\b',
    ]
    
    @classmethod
    def extract(cls, text: str) -> List[str]:
        """Extract remote indicators from text."""
        text_lower = text.lower()
        indicators = []
        
        for pattern in cls.POSITIVE_PATTERNS:
            if re.search(pattern, text_lower):
                indicators.append('remote')
                break
        
        for pattern in cls.HYBRID_PATTERNS:
            if re.search(pattern, text_lower):
                indicators.append('hybrid')
                break
        
        return indicators


class EmailExtractor:
    """Extracts public contact emails."""
    
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Skip these email patterns (likely not hiring contacts)
    SKIP_PATTERNS = [
        r'noreply',
        r'no-reply',
        r'support@',
        r'info@',
        r'sales@',
        r'marketing@',
        r'admin@',
        r'webmaster@',
        r'privacy@',
        r'legal@',
    ]
    
    # Prefer these patterns (likely hiring contacts)
    PREFER_PATTERNS = [
        r'careers?@',
        r'jobs?@',
        r'hiring@',
        r'recruiting?@',
        r'talent@',
        r'people@',
        r'hr@',
        r'team@',
    ]
    
    @classmethod
    def extract(cls, text: str) -> List[str]:
        """Extract relevant contact emails."""
        emails = re.findall(cls.EMAIL_PATTERN, text)
        
        # Filter and prioritize
        preferred = []
        other = []
        
        for email in set(emails):
            email_lower = email.lower()
            
            # Skip unwanted patterns
            if any(re.search(p, email_lower) for p in cls.SKIP_PATTERNS):
                continue
            
            # Prioritize hiring-related emails
            if any(re.search(p, email_lower) for p in cls.PREFER_PATTERNS):
                preferred.append(email)
            else:
                other.append(email)
        
        return preferred + other[:3]  # Return preferred + up to 3 others


# =============================================================================
# SCRAPER
# =============================================================================

class JobMarketScraper:
    """
    Main scraper for hidden job market intelligence.
    
    Tiers:
    - MVP: requests + BeautifulSoup
    - Beta: Add Playwright for JS rendering
    - Advanced: Add ML classification, change detection
    """
    
    DEFAULT_HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Common careers page paths to try
    CAREERS_PATHS = [
        '/careers',
        '/jobs',
        '/careers/',
        '/jobs/',
        '/work-with-us',
        '/join-us',
        '/about/careers',
        '/company/careers',
    ]
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        respect_robots: bool = True,
        rate_limit: bool = True
    ):
        self.config = self._load_config(config_path)
        self.respect_robots = respect_robots
        
        # Initialize components
        self.robots_checker = RobotsChecker() if respect_robots else None
        self.rate_limiter = RateLimiter(RateLimitConfig(
            min_delay_sec=self.config.get('extraction', {}).get('requests', {}).get('delay_min_sec', 2),
            max_delay_sec=self.config.get('extraction', {}).get('requests', {}).get('delay_max_sec', 5),
        )) if rate_limit else None
        
        self.tech_extractor = TechKeywordExtractor()
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        self.session.headers['User-Agent'] = self.config.get(
            'extraction', {}
        ).get('user_agent', 'HiddenJobMarketBot/1.0')
        
        # Results storage
        self.scraped_pages: List[ScrapedPage] = []
        self.company_profiles: Dict[str, CompanyProfile] = {}
    
    def _load_config(self, config_path: Optional[Path]) -> dict:
        """Load configuration."""
        if config_path is None:
            config_path = PROJECT_ROOT / 'config' / 'config.yaml'
        
        if not config_path.exists():
            config_path = PROJECT_ROOT / 'config' / 'config.example.yaml'
        
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    
    def _compute_hash(self, content: str) -> str:
        """Compute content hash for change detection."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _check_robots(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        if not self.robots_checker:
            return True
        return self.robots_checker.is_allowed(url)
    
    def _apply_rate_limit(self, domain: str):
        """Apply rate limiting before request."""
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed(domain)
    
    def _record_request(self, domain: str, success: bool, is_rate_limit: bool = False):
        """Record request for rate limiting."""
        if self.rate_limiter:
            if success:
                self.rate_limiter.record_request(domain)
            else:
                self.rate_limiter.record_error(domain, is_rate_limit)
    
    def fetch_page(self, url: str) -> Optional[Tuple[str, int]]:
        """
        Fetch a page with rate limiting and robots.txt compliance.
        
        Returns:
            Tuple of (html_content, status_code) or None if blocked/failed
        """
        domain = self._get_domain(url)
        
        # Check robots.txt
        if not self._check_robots(url):
            console.print(f"[yellow]Blocked by robots.txt: {url}[/yellow]")
            return None
        
        # Apply rate limiting
        self._apply_rate_limit(domain)
        
        try:
            timeout = self.config.get('extraction', {}).get('requests', {}).get('timeout_sec', 15)
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            
            self._record_request(domain, True)
            
            if response.status_code == 429:
                self._record_request(domain, False, is_rate_limit=True)
                console.print(f"[red]Rate limited: {url}[/red]")
                return None
            
            return response.text, response.status_code
            
        except requests.RequestException as e:
            self._record_request(domain, False)
            console.print(f"[red]Request failed: {url} - {e}[/red]")
            return None
    
    def scrape_page(self, url: str) -> Optional[ScrapedPage]:
        """
        Scrape a single page and extract all relevant data.
        
        Returns:
            ScrapedPage object or None if failed
        """
        result = self.fetch_page(url)
        if not result:
            return None
        
        html, status_code = result
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else ""
        
        # Get page text for analysis
        text = soup.get_text(separator=' ', strip=True)
        
        # Detect page type
        page_type = PageTypeDetector.detect(url, soup)
        
        # Extract data
        job_titles = JobTitleExtractor.extract(html, soup)
        tech_keywords = [kw for kw, _ in self.tech_extractor.extract(text)]
        hiring_signals = HiringSignalExtractor.extract(text)
        remote_indicators = RemoteIndicatorExtractor.extract(text)
        contact_emails = EmailExtractor.extract(text)
        
        # Check for apply button
        has_apply = bool(soup.find('a', string=re.compile(r'apply', re.I))) or \
                    bool(soup.find('button', string=re.compile(r'apply', re.I)))
        
        # Check for job listings (multiple job titles or listing structure)
        has_listings = len(job_titles) > 1 or \
                       bool(soup.find_all('div', class_=re.compile(r'job|position|opening', re.I)))
        
        page = ScrapedPage(
            url=url,
            domain=self._get_domain(url),
            title=title,
            content_hash=self._compute_hash(html),
            scraped_at=datetime.now(),
            status_code=status_code,
            page_type=page_type,
            job_titles=job_titles,
            tech_keywords=tech_keywords,
            hiring_signals=hiring_signals,
            remote_indicators=remote_indicators,
            contact_emails=contact_emails,
            has_apply_button=has_apply,
            has_job_listings=has_listings
        )
        
        self.scraped_pages.append(page)
        
        # Update company profile
        domain = page.domain
        if domain not in self.company_profiles:
            self.company_profiles[domain] = CompanyProfile(domain=domain, name=title.split('|')[0].strip())
        self.company_profiles[domain].merge_page(page)
        
        return page
    
    def discover_careers_page(self, base_url: str) -> Optional[str]:
        """
        Try to find the careers page for a domain.
        
        Returns:
            URL of careers page if found, None otherwise
        """
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        
        for path in self.CAREERS_PATHS:
            url = urljoin(base, path)
            result = self.fetch_page(url)
            
            if result:
                html, status_code = result
                if status_code == 200:
                    soup = BeautifulSoup(html, 'lxml')
                    page_type = PageTypeDetector.detect(url, soup)
                    if page_type == 'careers':
                        return url
        
        return None
    
    def scrape_domain(self, domain: str, max_pages: int = 5) -> CompanyProfile:
        """
        Scrape a domain for job-related content.
        
        Args:
            domain: Domain to scrape (e.g., 'example.com')
            max_pages: Maximum pages to scrape per domain
            
        Returns:
            CompanyProfile with aggregated data
        """
        base_url = f"https://{domain}"
        pages_scraped = 0
        
        # First, try to find careers page
        careers_url = self.discover_careers_page(base_url)
        
        if careers_url:
            page = self.scrape_page(careers_url)
            if page:
                pages_scraped += 1
                console.print(f"[green]Found careers page: {careers_url}[/green]")
        
        # Scrape homepage for additional signals
        if pages_scraped < max_pages:
            page = self.scrape_page(base_url)
            if page:
                pages_scraped += 1
        
        # Try about page
        if pages_scraped < max_pages:
            about_url = urljoin(base_url, '/about')
            page = self.scrape_page(about_url)
            if page:
                pages_scraped += 1
        
        return self.company_profiles.get(domain, CompanyProfile(domain=domain))
    
    def scrape_domains(self, domains: List[str], max_pages_per_domain: int = 5) -> List[CompanyProfile]:
        """Scrape multiple domains."""
        profiles = []
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Scraping domains...", total=len(domains))
            
            for domain in domains:
                profile = self.scrape_domain(domain, max_pages_per_domain)
                profiles.append(profile)
                progress.update(task, advance=1)
        
        return profiles
    
    def export_pages_csv(self, output_path: Path):
        """Export scraped pages to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if self.scraped_pages:
                fieldnames = list(self.scraped_pages[0].to_dict().keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for page in self.scraped_pages:
                    writer.writerow(page.to_dict())
        
        console.print(f"[green]Exported {len(self.scraped_pages)} pages to {output_path}[/green]")
    
    def export_profiles_csv(self, output_path: Path):
        """Export company profiles to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'domain', 'name', 'careers_url', 'job_titles', 'tech_keywords',
                'hiring_signals', 'remote_indicators', 'contact_emails',
                'pages_scraped', 'has_active_listings', 'first_seen', 'last_updated'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for profile in self.company_profiles.values():
                writer.writerow({
                    'domain': profile.domain,
                    'name': profile.name,
                    'careers_url': profile.careers_url or '',
                    'job_titles': json.dumps(list(profile.all_job_titles)),
                    'tech_keywords': json.dumps(list(profile.all_tech_keywords)),
                    'hiring_signals': json.dumps(list(profile.all_hiring_signals)),
                    'remote_indicators': json.dumps(list(profile.all_remote_indicators)),
                    'contact_emails': json.dumps(list(profile.all_contact_emails)),
                    'pages_scraped': profile.pages_scraped,
                    'has_active_listings': profile.has_active_listings,
                    'first_seen': profile.first_seen.isoformat() if profile.first_seen else '',
                    'last_updated': profile.last_updated.isoformat() if profile.last_updated else ''
                })
        
        console.print(f"[green]Exported {len(self.company_profiles)} profiles to {output_path}[/green]")


# =============================================================================
# CLI INTERFACE
# =============================================================================

@click.command()
@click.option('--url', '-u', help='Single URL to scrape')
@click.option('--domain', '-d', help='Single domain to scrape')
@click.option('--input', '-i', 'input_file', type=click.Path(exists=True), help='File with domains (one per line)')
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--max-pages', '-m', default=5, help='Max pages per domain')
@click.option('--no-robots', is_flag=True, help='Ignore robots.txt (not recommended)')
@click.option('--no-rate-limit', is_flag=True, help='Disable rate limiting (not recommended)')
def main(url, domain, input_file, output, max_pages, no_robots, no_rate_limit):
    """
    Scrape company websites for job market intelligence.
    
    Examples:
        python scraper.py --url https://example.com/careers
        python scraper.py --domain example.com
        python scraper.py --input domains.txt --output ./results
    """
    scraper = JobMarketScraper(
        respect_robots=not no_robots,
        rate_limit=not no_rate_limit
    )
    
    output_dir = Path(output) if output else PROJECT_ROOT / 'output' / 'scrape_results'
    
    if url:
        # Scrape single URL
        console.print(f"[cyan]Scraping URL: {url}[/cyan]")
        page = scraper.scrape_page(url)
        if page:
            console.print(f"[green]Success![/green]")
            console.print(f"  Title: {page.title}")
            console.print(f"  Type: {page.page_type}")
            console.print(f"  Job Titles: {page.job_titles}")
            console.print(f"  Tech Keywords: {page.tech_keywords}")
            console.print(f"  Hiring Signals: {page.hiring_signals}")
            console.print(f"  Remote: {page.remote_indicators}")
            console.print(f"  Emails: {page.contact_emails}")
    
    elif domain:
        # Scrape single domain
        console.print(f"[cyan]Scraping domain: {domain}[/cyan]")
        profile = scraper.scrape_domain(domain, max_pages)
        console.print(f"[green]Scraped {profile.pages_scraped} pages[/green]")
        
        # Export results
        scraper.export_profiles_csv(output_dir / 'profiles.csv')
        scraper.export_pages_csv(output_dir / 'pages.csv')
    
    elif input_file:
        # Scrape multiple domains from file
        with open(input_file) as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        console.print(f"[cyan]Scraping {len(domains)} domains...[/cyan]")
        profiles = scraper.scrape_domains(domains, max_pages)
        
        # Export results
        scraper.export_profiles_csv(output_dir / 'profiles.csv')
        scraper.export_pages_csv(output_dir / 'pages.csv')
        
        console.print(f"\n[bold green]Complete! Scraped {len(profiles)} domains.[/bold green]")
    
    else:
        console.print("[red]Please provide --url, --domain, or --input[/red]")
        raise click.Abort()


if __name__ == '__main__':
    main()
