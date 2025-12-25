"""
Domain Deduplication Utility

Handles deduplication of discovered domains across:
- Multiple dork queries
- Multiple discovery sessions
- Historical data

Features:
- Root domain extraction
- Fuzzy matching for similar domains
- Blocklist integration
"""

import re
from typing import Set, List, Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import dataclass
import csv

import yaml

try:
    import tldextract
    HAS_TLDEXTRACT = True
except ImportError:
    HAS_TLDEXTRACT = False

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass
class DomainInfo:
    """Parsed domain information."""
    original: str
    root_domain: str
    subdomain: str
    suffix: str
    is_valid: bool


class DomainDeduplicator:
    """
    Deduplicates domains from multiple sources.
    
    Handles:
    - URL to domain extraction
    - www prefix removal
    - Subdomain normalization
    - Blocklist filtering
    - Fuzzy duplicate detection
    """
    
    def __init__(self, blocklist_path: Optional[Path] = None):
        self.seen_domains: Set[str] = set()
        self.blocklist: Set[str] = set()
        self.blocklist_patterns: List[str] = []
        
        self._load_blocklist(blocklist_path)
    
    def _load_blocklist(self, path: Optional[Path]):
        """Load blocklist from YAML."""
        if path is None:
            path = PROJECT_ROOT / 'config' / 'blocklist.yaml'
        
        if not path.exists():
            return
        
        with open(path) as f:
            data = yaml.safe_load(f)
        
        # Load domain lists
        for category in ['job_boards', 'staffing_agencies', 'social_platforms', 
                         'news_media', 'gov_edu', 'spam_traps']:
            if category in data and isinstance(data[category], list):
                self.blocklist.update(d.lower() for d in data[category])
        
        # Load patterns
        if 'low_quality_patterns' in data:
            self.blocklist_patterns = data['low_quality_patterns']
    
    def extract_domain(self, url_or_domain: str) -> DomainInfo:
        """
        Extract root domain from URL or domain string.
        
        Examples:
            https://www.example.com/path -> example.com
            careers.example.co.uk -> example.co.uk
            example.io -> example.io
        """
        original = url_or_domain.strip().lower()
        
        # Handle full URLs
        if '://' in original:
            try:
                parsed = urlparse(original)
                domain = parsed.netloc
            except Exception:
                domain = original
        else:
            domain = original
        
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Use tldextract if available for better parsing
        if HAS_TLDEXTRACT:
            extracted = tldextract.extract(domain)
            root_domain = f"{extracted.domain}.{extracted.suffix}" if extracted.suffix else extracted.domain
            return DomainInfo(
                original=original,
                root_domain=root_domain,
                subdomain=extracted.subdomain,
                suffix=extracted.suffix,
                is_valid=bool(extracted.domain and extracted.suffix)
            )
        
        # Fallback: simple extraction
        parts = domain.split('.')
        if len(parts) >= 2:
            # Handle common multi-part TLDs
            multi_tlds = ['co.uk', 'com.au', 'co.nz', 'com.br', 'co.jp']
            for mtld in multi_tlds:
                if domain.endswith(mtld):
                    tld_parts = mtld.split('.')
                    root = '.'.join(parts[-(len(tld_parts)+1):])
                    return DomainInfo(
                        original=original,
                        root_domain=root,
                        subdomain='.'.join(parts[:-(len(tld_parts)+1)]),
                        suffix=mtld,
                        is_valid=True
                    )
            
            # Standard TLD
            root_domain = '.'.join(parts[-2:])
            subdomain = '.'.join(parts[:-2])
            return DomainInfo(
                original=original,
                root_domain=root_domain,
                subdomain=subdomain,
                suffix=parts[-1],
                is_valid=True
            )
        
        return DomainInfo(
            original=original,
            root_domain=domain,
            subdomain='',
            suffix='',
            is_valid=False
        )
    
    def is_blocked(self, domain: str) -> bool:
        """Check if domain is in blocklist."""
        domain_lower = domain.lower()
        
        # Direct match
        if domain_lower in self.blocklist:
            return True
        
        # Check if domain contains blocked domain
        for blocked in self.blocklist:
            if blocked in domain_lower:
                return True
        
        # Check patterns
        for pattern in self.blocklist_patterns:
            try:
                if re.match(pattern, domain_lower):
                    return True
            except re.error:
                pass
        
        return False
    
    def is_duplicate(self, domain: str) -> bool:
        """Check if domain was already seen."""
        info = self.extract_domain(domain)
        return info.root_domain in self.seen_domains
    
    def is_similar(self, domain1: str, domain2: str, threshold: float = 85.0) -> bool:
        """
        Check if two domains are similar (fuzzy match).
        
        Useful for catching:
        - acme.io vs acme.com
        - acme-inc.com vs acmeinc.com
        """
        if not HAS_RAPIDFUZZ:
            return domain1 == domain2
        
        info1 = self.extract_domain(domain1)
        info2 = self.extract_domain(domain2)
        
        # Compare just the domain name part (without TLD)
        name1 = info1.root_domain.split('.')[0]
        name2 = info2.root_domain.split('.')[0]
        
        similarity = fuzz.ratio(name1, name2)
        return similarity >= threshold
    
    def add(self, url_or_domain: str) -> Tuple[bool, str]:
        """
        Add a domain if it's new and not blocked.
        
        Returns:
            Tuple of (was_added, reason)
        """
        info = self.extract_domain(url_or_domain)
        
        if not info.is_valid:
            return False, "invalid_domain"
        
        if self.is_blocked(info.root_domain):
            return False, "blocked"
        
        if info.root_domain in self.seen_domains:
            return False, "duplicate"
        
        self.seen_domains.add(info.root_domain)
        return True, "added"
    
    def add_batch(self, urls_or_domains: List[str]) -> dict:
        """
        Add multiple domains and return statistics.
        
        Returns:
            Dict with counts: added, blocked, duplicate, invalid
        """
        stats = {'added': 0, 'blocked': 0, 'duplicate': 0, 'invalid': 0}
        
        for item in urls_or_domains:
            added, reason = self.add(item)
            if added:
                stats['added'] += 1
            elif reason == 'blocked':
                stats['blocked'] += 1
            elif reason == 'duplicate':
                stats['duplicate'] += 1
            else:
                stats['invalid'] += 1
        
        return stats
    
    def find_similar_domains(self, domains: List[str], threshold: float = 85.0) -> List[Tuple[str, str, float]]:
        """
        Find potentially similar domains in a list.
        
        Returns list of (domain1, domain2, similarity_score) tuples.
        """
        if not HAS_RAPIDFUZZ:
            return []
        
        similar = []
        domain_list = list(domains)
        
        for i, d1 in enumerate(domain_list):
            for d2 in domain_list[i+1:]:
                info1 = self.extract_domain(d1)
                info2 = self.extract_domain(d2)
                
                name1 = info1.root_domain.split('.')[0]
                name2 = info2.root_domain.split('.')[0]
                
                score = fuzz.ratio(name1, name2)
                if score >= threshold and score < 100:  # Not exact match
                    similar.append((d1, d2, score))
        
        return sorted(similar, key=lambda x: x[2], reverse=True)
    
    def load_history(self, csv_path: Path):
        """Load previously seen domains from CSV."""
        if not csv_path.exists():
            return
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                domain = row.get('domain', '')
                if domain:
                    info = self.extract_domain(domain)
                    self.seen_domains.add(info.root_domain)
    
    def export(self, output_path: Path):
        """Export unique domains to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for domain in sorted(self.seen_domains):
                f.write(f"{domain}\n")
    
    def get_stats(self) -> dict:
        """Get deduplication statistics."""
        return {
            'unique_domains': len(self.seen_domains),
            'blocklist_size': len(self.blocklist),
            'pattern_count': len(self.blocklist_patterns)
        }
