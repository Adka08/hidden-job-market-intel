"""
Rate Limiter for Ethical Web Scraping

Implements configurable rate limiting to respect server resources
and avoid being blocked.
"""

import time
import random
from datetime import datetime, timedelta
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import threading


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    min_delay_sec: float = 2.0
    max_delay_sec: float = 5.0
    requests_per_minute: int = 10
    requests_per_domain_per_hour: int = 20
    backoff_multiplier: float = 2.0
    max_backoff_sec: float = 300.0


@dataclass
class DomainState:
    """Tracks request state for a domain."""
    request_times: list = field(default_factory=list)
    consecutive_errors: int = 0
    last_error_time: Optional[datetime] = None
    backoff_until: Optional[datetime] = None


class RateLimiter:
    """
    Thread-safe rate limiter with per-domain tracking.
    
    Features:
    - Configurable delays between requests
    - Per-domain request limits
    - Exponential backoff on errors
    - Jitter to avoid detection patterns
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._domain_states: Dict[str, DomainState] = defaultdict(DomainState)
        self._lock = threading.Lock()
        self._last_request_time: Optional[datetime] = None
    
    def _get_jittered_delay(self) -> float:
        """Get a random delay within configured bounds."""
        return random.uniform(
            self.config.min_delay_sec,
            self.config.max_delay_sec
        )
    
    def _clean_old_requests(self, state: DomainState, window_minutes: int = 60):
        """Remove request times older than the window."""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        state.request_times = [t for t in state.request_times if t > cutoff]
    
    def can_request(self, domain: str) -> bool:
        """Check if a request to the domain is allowed."""
        with self._lock:
            state = self._domain_states[domain]
            
            # Check backoff
            if state.backoff_until and datetime.now() < state.backoff_until:
                return False
            
            # Clean old requests
            self._clean_old_requests(state)
            
            # Check per-domain limit
            if len(state.request_times) >= self.config.requests_per_domain_per_hour:
                return False
            
            return True
    
    def wait_if_needed(self, domain: str) -> float:
        """
        Wait the appropriate amount of time before making a request.
        
        Returns:
            The number of seconds waited
        """
        with self._lock:
            state = self._domain_states[domain]
            waited = 0.0
            
            # Wait for backoff if needed
            if state.backoff_until:
                wait_time = (state.backoff_until - datetime.now()).total_seconds()
                if wait_time > 0:
                    time.sleep(wait_time)
                    waited += wait_time
                state.backoff_until = None
            
            # Wait for minimum delay since last request
            if self._last_request_time:
                elapsed = (datetime.now() - self._last_request_time).total_seconds()
                min_delay = self._get_jittered_delay()
                if elapsed < min_delay:
                    sleep_time = min_delay - elapsed
                    time.sleep(sleep_time)
                    waited += sleep_time
            
            return waited
    
    def record_request(self, domain: str):
        """Record a successful request."""
        with self._lock:
            state = self._domain_states[domain]
            state.request_times.append(datetime.now())
            state.consecutive_errors = 0
            self._last_request_time = datetime.now()
    
    def record_error(self, domain: str, is_rate_limit: bool = False):
        """
        Record a failed request and apply backoff if needed.
        
        Args:
            domain: The domain that returned an error
            is_rate_limit: True if the error was a 429 or similar
        """
        with self._lock:
            state = self._domain_states[domain]
            state.consecutive_errors += 1
            state.last_error_time = datetime.now()
            
            # Calculate backoff
            if is_rate_limit or state.consecutive_errors >= 3:
                backoff_sec = min(
                    self.config.min_delay_sec * (
                        self.config.backoff_multiplier ** state.consecutive_errors
                    ),
                    self.config.max_backoff_sec
                )
                state.backoff_until = datetime.now() + timedelta(seconds=backoff_sec)
    
    def get_stats(self, domain: str) -> dict:
        """Get rate limiting stats for a domain."""
        with self._lock:
            state = self._domain_states[domain]
            self._clean_old_requests(state)
            
            return {
                'domain': domain,
                'requests_last_hour': len(state.request_times),
                'consecutive_errors': state.consecutive_errors,
                'in_backoff': state.backoff_until is not None and datetime.now() < state.backoff_until,
                'backoff_until': state.backoff_until.isoformat() if state.backoff_until else None
            }
    
    def reset_domain(self, domain: str):
        """Reset rate limiting state for a domain."""
        with self._lock:
            self._domain_states[domain] = DomainState()


class AdaptiveRateLimiter(RateLimiter):
    """
    Rate limiter that adapts based on server response times.
    
    Slower responses = longer delays (server under load)
    Faster responses = shorter delays (within bounds)
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        super().__init__(config)
        self._response_times: Dict[str, list] = defaultdict(list)
        self._max_response_history = 10
    
    def record_response_time(self, domain: str, response_time_sec: float):
        """Record response time for adaptive delay calculation."""
        with self._lock:
            times = self._response_times[domain]
            times.append(response_time_sec)
            if len(times) > self._max_response_history:
                times.pop(0)
    
    def get_adaptive_delay(self, domain: str) -> float:
        """Get delay adjusted based on server response times."""
        with self._lock:
            times = self._response_times.get(domain, [])
            
            if not times:
                return self._get_jittered_delay()
            
            avg_response = sum(times) / len(times)
            
            # If server is slow (>2s avg), increase delay
            if avg_response > 2.0:
                multiplier = min(avg_response / 2.0, 3.0)
                base_delay = self._get_jittered_delay()
                return base_delay * multiplier
            
            return self._get_jittered_delay()
