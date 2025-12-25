"""
robots.txt Compliance Checker

Ensures ethical scraping by respecting robots.txt directives.
Caches results to minimize repeated requests.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass
import requests


@dataclass
class RobotsRule:
    """Represents a parsed robots.txt rule."""
    user_agent: str
    allowed_paths: list
    disallowed_paths: list
    crawl_delay: Optional[float] = None


@dataclass
class RobotsCache:
    """Cached robots.txt data for a domain."""
    rules: Dict[str, RobotsRule]
    fetched_at: datetime
    raw_content: str
    status_code: int


class RobotsChecker:
    """
    Checks robots.txt compliance before scraping.
    
    Features:
    - Caches robots.txt per domain
    - Supports wildcard matching
    - Extracts crawl-delay directives
    - Handles missing/invalid robots.txt gracefully
    """
    
    USER_AGENT = "HiddenJobMarketBot"
    CACHE_DURATION_HOURS = 24
    
    def __init__(self, user_agent: str = None, cache_hours: int = 24):
        self.user_agent = user_agent or self.USER_AGENT
        self.cache_hours = cache_hours
        self._cache: Dict[str, RobotsCache] = {}
    
    def _get_robots_url(self, url: str) -> str:
        """Get the robots.txt URL for a given URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()
    
    def _fetch_robots(self, url: str, timeout: int = 10) -> Tuple[str, int]:
        """Fetch robots.txt content."""
        robots_url = self._get_robots_url(url)
        
        try:
            response = requests.get(
                robots_url,
                timeout=timeout,
                headers={'User-Agent': self.user_agent}
            )
            return response.text, response.status_code
        except requests.RequestException:
            return "", 0
    
    def _parse_robots(self, content: str) -> Dict[str, RobotsRule]:
        """Parse robots.txt content into rules."""
        rules = {}
        current_agents = []
        current_allowed = []
        current_disallowed = []
        current_delay = None
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse directive
            if ':' in line:
                directive, value = line.split(':', 1)
                directive = directive.strip().lower()
                value = value.strip()
                
                if directive == 'user-agent':
                    # Save previous agent rules
                    if current_agents:
                        for agent in current_agents:
                            rules[agent.lower()] = RobotsRule(
                                user_agent=agent,
                                allowed_paths=current_allowed.copy(),
                                disallowed_paths=current_disallowed.copy(),
                                crawl_delay=current_delay
                            )
                    
                    # Start new agent
                    current_agents = [value]
                    current_allowed = []
                    current_disallowed = []
                    current_delay = None
                    
                elif directive == 'allow':
                    current_allowed.append(value)
                    
                elif directive == 'disallow':
                    current_disallowed.append(value)
                    
                elif directive == 'crawl-delay':
                    try:
                        current_delay = float(value)
                    except ValueError:
                        pass
        
        # Save last agent rules
        if current_agents:
            for agent in current_agents:
                rules[agent.lower()] = RobotsRule(
                    user_agent=agent,
                    allowed_paths=current_allowed.copy(),
                    disallowed_paths=current_disallowed.copy(),
                    crawl_delay=current_delay
                )
        
        return rules
    
    def _is_cache_valid(self, domain: str) -> bool:
        """Check if cached robots.txt is still valid."""
        if domain not in self._cache:
            return False
        
        cache = self._cache[domain]
        age = datetime.now() - cache.fetched_at
        return age < timedelta(hours=self.cache_hours)
    
    def _match_path(self, pattern: str, path: str) -> bool:
        """Check if a path matches a robots.txt pattern."""
        if not pattern:
            return False
        
        # Convert robots.txt pattern to regex
        # * matches any sequence, $ matches end of URL
        regex_pattern = re.escape(pattern)
        regex_pattern = regex_pattern.replace(r'\*', '.*')
        regex_pattern = regex_pattern.replace(r'\$', '$')
        
        if not regex_pattern.endswith('$'):
            regex_pattern += '.*'
        
        try:
            return bool(re.match(regex_pattern, path))
        except re.error:
            return False
    
    def get_rules(self, url: str) -> Optional[RobotsCache]:
        """Get robots.txt rules for a URL, fetching if needed."""
        domain = self._get_domain(url)
        
        # Check cache
        if self._is_cache_valid(domain):
            return self._cache[domain]
        
        # Fetch and parse
        content, status_code = self._fetch_robots(url)
        rules = self._parse_robots(content) if content else {}
        
        cache = RobotsCache(
            rules=rules,
            fetched_at=datetime.now(),
            raw_content=content,
            status_code=status_code
        )
        
        self._cache[domain] = cache
        return cache
    
    def is_allowed(self, url: str) -> bool:
        """
        Check if scraping a URL is allowed by robots.txt.
        
        Returns True if:
        - robots.txt doesn't exist (404)
        - robots.txt can't be fetched (network error)
        - Path is explicitly allowed
        - Path is not disallowed
        
        Returns False if:
        - Path is explicitly disallowed for our user agent
        - Path is disallowed for all agents (*)
        """
        cache = self.get_rules(url)
        
        # No robots.txt or fetch error = allowed
        if not cache or cache.status_code in (0, 404):
            return True
        
        parsed = urlparse(url)
        path = parsed.path or '/'
        
        # Check rules for our user agent first, then wildcard
        for agent_pattern in [self.user_agent.lower(), '*']:
            if agent_pattern not in cache.rules:
                continue
            
            rule = cache.rules[agent_pattern]
            
            # Check allowed paths first (they take precedence)
            for allowed in rule.allowed_paths:
                if self._match_path(allowed, path):
                    return True
            
            # Check disallowed paths
            for disallowed in rule.disallowed_paths:
                if self._match_path(disallowed, path):
                    return False
        
        # Not explicitly disallowed = allowed
        return True
    
    def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get the crawl-delay directive for a URL's domain."""
        cache = self.get_rules(url)
        
        if not cache:
            return None
        
        # Check our user agent first, then wildcard
        for agent_pattern in [self.user_agent.lower(), '*']:
            if agent_pattern in cache.rules:
                delay = cache.rules[agent_pattern].crawl_delay
                if delay is not None:
                    return delay
        
        return None
    
    def get_status(self, url: str) -> dict:
        """Get detailed robots.txt status for a URL."""
        domain = self._get_domain(url)
        cache = self.get_rules(url)
        
        return {
            'domain': domain,
            'robots_url': self._get_robots_url(url),
            'status_code': cache.status_code if cache else None,
            'is_allowed': self.is_allowed(url),
            'crawl_delay': self.get_crawl_delay(url),
            'cached': self._is_cache_valid(domain),
            'cache_age_hours': (
                (datetime.now() - cache.fetched_at).total_seconds() / 3600
                if cache else None
            )
        }
    
    def clear_cache(self, domain: Optional[str] = None):
        """Clear cached robots.txt data."""
        if domain:
            self._cache.pop(domain, None)
        else:
            self._cache.clear()
