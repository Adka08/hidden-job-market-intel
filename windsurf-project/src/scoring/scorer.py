"""
Lead Scoring Engine for Hidden Job Market Intelligence

Scores company leads based on:
- Role match (target roles found)
- Tech stack match (relevant technologies)
- Hiring signals (active hiring indicators)
- Company signals (funding, growth)
- Recency (how fresh the data is)

Usage:
    python scorer.py --input profiles.csv --output scored_leads.csv
    python scorer.py --database leads.db --export csv
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
import csv

import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import click

console = Console()


# =============================================================================
# SCORING CONFIGURATION
# =============================================================================

@dataclass
class ScoringWeights:
    """Configurable weights for scoring components."""
    role_match: float = 0.30
    tech_match: float = 0.25
    hiring_signals: float = 0.20
    company_signals: float = 0.15
    recency: float = 0.10
    
    def validate(self) -> bool:
        """Ensure weights sum to 1.0"""
        total = self.role_match + self.tech_match + self.hiring_signals + \
                self.company_signals + self.recency
        return abs(total - 1.0) < 0.01


@dataclass
class ScoringConfig:
    """Full scoring configuration."""
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    min_lead_score: int = 40
    high_priority_score: int = 70
    
    # Role matching
    target_roles: List[str] = field(default_factory=list)
    target_seniority: List[str] = field(default_factory=list)
    
    # Tech matching
    tech_weights: Dict[str, float] = field(default_factory=dict)
    
    # Recency settings
    fresh_days: int = 7  # Full recency score if within this many days
    stale_days: int = 30  # Zero recency score after this many days


# =============================================================================
# SCORING DATA STRUCTURES
# =============================================================================

@dataclass
class LeadScore:
    """Detailed score breakdown for a lead."""
    domain: str
    total_score: float  # 0-100
    
    # Component scores (0-100 each, before weighting)
    role_score: float = 0.0
    tech_score: float = 0.0
    hiring_score: float = 0.0
    company_score: float = 0.0
    recency_score: float = 0.0
    
    # Weighted contributions
    role_contribution: float = 0.0
    tech_contribution: float = 0.0
    hiring_contribution: float = 0.0
    company_contribution: float = 0.0
    recency_contribution: float = 0.0
    
    # Match details
    matched_roles: List[str] = field(default_factory=list)
    matched_techs: List[str] = field(default_factory=list)
    matched_signals: List[str] = field(default_factory=list)
    
    # Classification
    priority: str = "low"  # low, medium, high
    
    # Metadata
    scored_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'domain': self.domain,
            'total_score': round(self.total_score, 2),
            'priority': self.priority,
            'role_score': round(self.role_score, 2),
            'tech_score': round(self.tech_score, 2),
            'hiring_score': round(self.hiring_score, 2),
            'company_score': round(self.company_score, 2),
            'recency_score': round(self.recency_score, 2),
            'matched_roles': json.dumps(self.matched_roles),
            'matched_techs': json.dumps(self.matched_techs),
            'matched_signals': json.dumps(self.matched_signals),
            'scored_at': self.scored_at.isoformat()
        }


@dataclass
class CompanyData:
    """Input data for scoring a company."""
    domain: str
    name: str = ""
    careers_url: str = ""
    
    job_titles: List[str] = field(default_factory=list)
    tech_keywords: List[str] = field(default_factory=list)
    hiring_signals: List[str] = field(default_factory=list)
    remote_indicators: List[str] = field(default_factory=list)
    contact_emails: List[str] = field(default_factory=list)
    
    has_active_listings: bool = False
    pages_scraped: int = 0
    
    first_seen: Optional[datetime] = None
    last_updated: Optional[datetime] = None


# =============================================================================
# SCORING ENGINE
# =============================================================================

class LeadScorer:
    """
    Scores company leads based on configurable criteria.
    
    Scoring Formula:
    
    TOTAL_SCORE = (
        ROLE_SCORE * weight_role +
        TECH_SCORE * weight_tech +
        HIRING_SCORE * weight_hiring +
        COMPANY_SCORE * weight_company +
        RECENCY_SCORE * weight_recency
    )
    
    Each component score is 0-100, weights sum to 1.0.
    Final score is 0-100.
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None, config_path: Optional[Path] = None):
        self.config = config or self._load_config(config_path)
        self._load_keywords()
        self._load_roles()
    
    def _load_config(self, config_path: Optional[Path]) -> ScoringConfig:
        """Load scoring configuration from YAML."""
        if config_path is None:
            config_path = PROJECT_ROOT / 'config' / 'config.yaml'
        
        if not config_path.exists():
            config_path = PROJECT_ROOT / 'config' / 'config.example.yaml'
        
        config = ScoringConfig()
        
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
                
                # Load weights
                weights_data = data.get('scoring', {}).get('weights', {})
                config.weights = ScoringWeights(
                    role_match=weights_data.get('role_match', 0.30),
                    tech_match=weights_data.get('tech_match', 0.25),
                    hiring_signals=weights_data.get('hiring_signals', 0.20),
                    company_signals=weights_data.get('company_signals', 0.15),
                    recency=weights_data.get('recency', 0.10)
                )
                
                # Load thresholds
                config.min_lead_score = data.get('scoring', {}).get('min_lead_score', 40)
                config.high_priority_score = data.get('scoring', {}).get('high_priority_score', 70)
                
                # Load target roles
                config.target_roles = data.get('profile', {}).get('target_roles', [])
                config.target_seniority = data.get('profile', {}).get('seniority', [])
        
        return config
    
    def _load_keywords(self):
        """Load tech keywords and weights."""
        keywords_path = PROJECT_ROOT / 'config' / 'keywords.yaml'
        self.tech_weights = {}
        
        if keywords_path.exists():
            with open(keywords_path) as f:
                data = yaml.safe_load(f)
                
                for category in ['languages', 'data_ml', 'infrastructure', 'databases']:
                    if category in data:
                        for keyword, info in data[category].items():
                            weight = info.get('weight', 0.5)
                            self.tech_weights[keyword.lower()] = weight
                            # Add aliases
                            for alias in info.get('aliases', []):
                                self.tech_weights[alias.lower()] = weight
        
        # Fallback defaults
        if not self.tech_weights:
            self.tech_weights = {
                'python': 1.0, 'spark': 1.0, 'airflow': 1.0, 'pytorch': 1.0,
                'kubernetes': 0.8, 'aws': 0.9, 'sql': 1.0, 'kafka': 0.9
            }
    
    def _load_roles(self):
        """Load target role patterns."""
        roles_path = PROJECT_ROOT / 'config' / 'roles.yaml'
        self.role_patterns = {}
        self.seniority_multipliers = {}
        
        if roles_path.exists():
            with open(roles_path) as f:
                data = yaml.safe_load(f)
                
                # Primary roles
                for role_name, info in data.get('primary_roles', {}).items():
                    for pattern in info.get('patterns', []):
                        self.role_patterns[pattern.lower()] = info.get('weight', 1.0)
                
                # Secondary roles
                for role_name, info in data.get('secondary_roles', {}).items():
                    for pattern in info.get('patterns', []):
                        self.role_patterns[pattern.lower()] = info.get('weight', 0.7)
                
                # Seniority
                for level, info in data.get('seniority', {}).items():
                    for pattern in info.get('patterns', []):
                        if pattern:
                            self.seniority_multipliers[pattern.lower()] = info.get('multiplier', 1.0)
        
        # Fallback defaults
        if not self.role_patterns:
            self.role_patterns = {
                'data engineer': 1.0, 'backend engineer': 1.0, 'ml engineer': 1.0,
                'software engineer': 0.7, 'python developer': 0.9
            }
    
    def score_role_match(self, company: CompanyData) -> Tuple[float, List[str]]:
        """
        Score based on matching job titles.
        
        Logic:
        - Check each job title against target role patterns
        - Apply seniority multipliers
        - Return best match score (0-100)
        """
        if not company.job_titles:
            return 0.0, []
        
        matched = []
        best_score = 0.0
        
        for title in company.job_titles:
            title_lower = title.lower()
            
            # Check role patterns
            for pattern, weight in self.role_patterns.items():
                if pattern in title_lower:
                    # Apply seniority multiplier
                    multiplier = 1.0
                    for seniority, mult in self.seniority_multipliers.items():
                        if seniority in title_lower:
                            multiplier = mult
                            break
                    
                    score = weight * multiplier * 100
                    if score > best_score:
                        best_score = score
                    
                    if title not in matched:
                        matched.append(title)
        
        return min(best_score, 100.0), matched
    
    def score_tech_match(self, company: CompanyData) -> Tuple[float, List[str]]:
        """
        Score based on matching technologies.
        
        Logic:
        - Sum weights of matched tech keywords
        - Normalize to 0-100 (cap at 5 high-weight matches = 100)
        """
        if not company.tech_keywords:
            return 0.0, []
        
        matched = []
        total_weight = 0.0
        
        for tech in company.tech_keywords:
            tech_lower = tech.lower()
            if tech_lower in self.tech_weights:
                weight = self.tech_weights[tech_lower]
                total_weight += weight
                matched.append(tech)
        
        # Normalize: 5 high-weight (1.0) matches = 100
        score = min((total_weight / 5.0) * 100, 100.0)
        
        return score, matched
    
    def score_hiring_signals(self, company: CompanyData) -> Tuple[float, List[str]]:
        """
        Score based on hiring signals.
        
        Logic:
        - Strong signals (we're hiring, open positions): 30 points each
        - Moderate signals (careers page exists): 20 points
        - Active listings: 40 points
        - Cap at 100
        """
        score = 0.0
        matched = []
        
        # Check for strong hiring signals
        strong_signals = ['hiring:', 'we\'re hiring', 'now hiring', 'open positions']
        for signal in company.hiring_signals:
            signal_lower = signal.lower()
            for strong in strong_signals:
                if strong in signal_lower:
                    score += 30
                    matched.append(signal)
                    break
        
        # Active job listings
        if company.has_active_listings:
            score += 40
            matched.append('active_listings')
        
        # Has careers page
        if company.careers_url:
            score += 20
            matched.append('careers_page')
        
        return min(score, 100.0), matched
    
    def score_company_signals(self, company: CompanyData) -> Tuple[float, List[str]]:
        """
        Score based on company signals (funding, growth).
        
        Logic:
        - Funding signals (series A/B/C): 40 points
        - Growth signals (expanding, scaling): 30 points
        - Remote indicators: 20 points
        - Contact emails available: 10 points
        """
        score = 0.0
        matched = []
        
        # Check funding signals
        funding_keywords = ['series', 'raised', 'backed', 'funding', 'yc', 'combinator']
        for signal in company.hiring_signals:
            signal_lower = signal.lower()
            for keyword in funding_keywords:
                if keyword in signal_lower:
                    score += 40
                    matched.append(f'funding:{signal}')
                    break
        
        # Growth signals
        growth_keywords = ['growing', 'expanding', 'scaling']
        for signal in company.hiring_signals:
            signal_lower = signal.lower()
            for keyword in growth_keywords:
                if keyword in signal_lower:
                    score += 30
                    matched.append(f'growth:{signal}')
                    break
        
        # Remote indicators
        if company.remote_indicators:
            score += 20
            matched.extend([f'remote:{r}' for r in company.remote_indicators])
        
        # Contact emails
        if company.contact_emails:
            score += 10
            matched.append('has_contact')
        
        return min(score, 100.0), matched
    
    def score_recency(self, company: CompanyData) -> float:
        """
        Score based on data freshness.
        
        Logic:
        - Within fresh_days: 100
        - Between fresh_days and stale_days: linear decay
        - After stale_days: 0
        """
        if not company.last_updated:
            return 50.0  # Unknown = neutral
        
        age_days = (datetime.now() - company.last_updated).days
        
        if age_days <= self.config.fresh_days:
            return 100.0
        elif age_days >= self.config.stale_days:
            return 0.0
        else:
            # Linear decay
            decay_range = self.config.stale_days - self.config.fresh_days
            days_past_fresh = age_days - self.config.fresh_days
            return 100.0 * (1 - days_past_fresh / decay_range)
    
    def score_company(self, company: CompanyData) -> LeadScore:
        """
        Calculate full score for a company.
        
        Returns:
            LeadScore with detailed breakdown
        """
        weights = self.config.weights
        
        # Calculate component scores
        role_score, matched_roles = self.score_role_match(company)
        tech_score, matched_techs = self.score_tech_match(company)
        hiring_score, hiring_signals = self.score_hiring_signals(company)
        company_score, company_signals = self.score_company_signals(company)
        recency_score = self.score_recency(company)
        
        # Calculate weighted contributions
        role_contribution = role_score * weights.role_match
        tech_contribution = tech_score * weights.tech_match
        hiring_contribution = hiring_score * weights.hiring_signals
        company_contribution = company_score * weights.company_signals
        recency_contribution = recency_score * weights.recency
        
        # Total score
        total_score = (
            role_contribution +
            tech_contribution +
            hiring_contribution +
            company_contribution +
            recency_contribution
        )
        
        # Determine priority
        if total_score >= self.config.high_priority_score:
            priority = "high"
        elif total_score >= self.config.min_lead_score:
            priority = "medium"
        else:
            priority = "low"
        
        return LeadScore(
            domain=company.domain,
            total_score=total_score,
            role_score=role_score,
            tech_score=tech_score,
            hiring_score=hiring_score,
            company_score=company_score,
            recency_score=recency_score,
            role_contribution=role_contribution,
            tech_contribution=tech_contribution,
            hiring_contribution=hiring_contribution,
            company_contribution=company_contribution,
            recency_contribution=recency_contribution,
            matched_roles=matched_roles,
            matched_techs=matched_techs,
            matched_signals=hiring_signals + company_signals,
            priority=priority
        )
    
    def score_companies(self, companies: List[CompanyData]) -> List[LeadScore]:
        """Score multiple companies and sort by score."""
        scores = []
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Scoring leads...", total=len(companies))
            
            for company in companies:
                score = self.score_company(company)
                scores.append(score)
                progress.update(task, advance=1)
        
        # Sort by total score descending
        scores.sort(key=lambda x: x.total_score, reverse=True)
        
        return scores
    
    def filter_leads(
        self,
        scores: List[LeadScore],
        min_score: Optional[float] = None,
        priority: Optional[str] = None
    ) -> List[LeadScore]:
        """Filter scored leads by criteria."""
        if min_score is None:
            min_score = self.config.min_lead_score
        
        filtered = [s for s in scores if s.total_score >= min_score]
        
        if priority:
            filtered = [s for s in filtered if s.priority == priority]
        
        return filtered
    
    def display_scores(self, scores: List[LeadScore], limit: int = 20):
        """Display scores in a formatted table."""
        table = Table(title=f"Top {min(limit, len(scores))} Leads")
        
        table.add_column("Domain", style="cyan")
        table.add_column("Score", style="green", justify="right")
        table.add_column("Priority", style="yellow")
        table.add_column("Role", justify="right")
        table.add_column("Tech", justify="right")
        table.add_column("Hiring", justify="right")
        table.add_column("Matched Roles", max_width=30)
        
        for score in scores[:limit]:
            priority_color = {
                'high': '[bold green]',
                'medium': '[yellow]',
                'low': '[dim]'
            }.get(score.priority, '')
            
            table.add_row(
                score.domain,
                f"{score.total_score:.1f}",
                f"{priority_color}{score.priority}[/]",
                f"{score.role_score:.0f}",
                f"{score.tech_score:.0f}",
                f"{score.hiring_score:.0f}",
                ", ".join(score.matched_roles[:2]) if score.matched_roles else "-"
            )
        
        console.print(table)
    
    def export_csv(self, scores: List[LeadScore], output_path: Path):
        """Export scores to CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if scores:
                fieldnames = list(scores[0].to_dict().keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for score in scores:
                    writer.writerow(score.to_dict())
        
        console.print(f"[green]Exported {len(scores)} scores to {output_path}[/green]")


# =============================================================================
# DATA LOADING
# =============================================================================

def load_companies_from_csv(csv_path: Path) -> List[CompanyData]:
    """Load company data from CSV (output of scraper)."""
    companies = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            company = CompanyData(
                domain=row.get('domain', ''),
                name=row.get('name', ''),
                careers_url=row.get('careers_url', ''),
                job_titles=json.loads(row.get('job_titles', '[]')),
                tech_keywords=json.loads(row.get('tech_keywords', '[]')),
                hiring_signals=json.loads(row.get('hiring_signals', '[]')),
                remote_indicators=json.loads(row.get('remote_indicators', '[]')),
                contact_emails=json.loads(row.get('contact_emails', '[]')),
                has_active_listings=row.get('has_active_listings', '').lower() == 'true',
                pages_scraped=int(row.get('pages_scraped', 0))
            )
            
            # Parse dates
            if row.get('first_seen'):
                try:
                    company.first_seen = datetime.fromisoformat(row['first_seen'])
                except ValueError:
                    pass
            
            if row.get('last_updated'):
                try:
                    company.last_updated = datetime.fromisoformat(row['last_updated'])
                except ValueError:
                    pass
            
            companies.append(company)
    
    return companies


# =============================================================================
# CLI INTERFACE
# =============================================================================

@click.command()
@click.option('--input', '-i', 'input_file', type=click.Path(exists=True), help='Input CSV with company profiles')
@click.option('--output', '-o', type=click.Path(), help='Output CSV path')
@click.option('--min-score', '-m', type=float, help='Minimum score threshold')
@click.option('--priority', '-p', type=click.Choice(['high', 'medium', 'low']), help='Filter by priority')
@click.option('--limit', '-l', default=50, help='Max leads to display/export')
@click.option('--show-all', is_flag=True, help='Show all scores including low priority')
def main(input_file, output, min_score, priority, limit, show_all):
    """
    Score company leads based on job market signals.
    
    Examples:
        python scorer.py --input profiles.csv --output scored_leads.csv
        python scorer.py --input profiles.csv --priority high --limit 20
    """
    if not input_file:
        # Try default location
        default_input = PROJECT_ROOT / 'output' / 'scrape_results' / 'profiles.csv'
        if default_input.exists():
            input_file = str(default_input)
        else:
            console.print("[red]Please provide --input CSV file[/red]")
            raise click.Abort()
    
    # Load data
    console.print(f"[cyan]Loading companies from {input_file}...[/cyan]")
    companies = load_companies_from_csv(Path(input_file))
    console.print(f"[green]Loaded {len(companies)} companies[/green]")
    
    # Score
    scorer = LeadScorer()
    scores = scorer.score_companies(companies)
    
    # Filter
    if not show_all:
        scores = scorer.filter_leads(scores, min_score=min_score, priority=priority)
    
    # Display
    scorer.display_scores(scores, limit=limit)
    
    # Summary
    high_count = len([s for s in scores if s.priority == 'high'])
    medium_count = len([s for s in scores if s.priority == 'medium'])
    low_count = len([s for s in scores if s.priority == 'low'])
    
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  [green]High priority:[/green] {high_count}")
    console.print(f"  [yellow]Medium priority:[/yellow] {medium_count}")
    console.print(f"  [dim]Low priority:[/dim] {low_count}")
    
    # Export
    if output:
        output_path = Path(output)
    else:
        output_path = PROJECT_ROOT / 'output' / 'reports' / f'scored_leads_{datetime.now().strftime("%Y%m%d")}.csv'
    
    scorer.export_csv(scores[:limit], output_path)


if __name__ == '__main__':
    main()
