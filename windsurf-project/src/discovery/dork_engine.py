"""
Google Dorking Engine for Hidden Job Market Discovery

This module generates and manages Google dork queries for discovering
company career pages and hiring signals before they appear on job boards.

Usage:
    python dork_engine.py --category careers --output urls.txt
    python dork_engine.py --all --export csv
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field, asdict
from urllib.parse import quote_plus, urlparse
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
# DATA CLASSES
# =============================================================================

@dataclass
class DorkTemplate:
    """Represents a single Google dork template."""
    name: str
    category: str
    template: str
    description: str
    use_case: str
    priority: int = 1  # 1=high, 2=medium, 3=low
    
    def build(self, **kwargs) -> str:
        """Build the dork query with variable substitution."""
        query = self.template
        for key, value in kwargs.items():
            query = query.replace(f"{{{key}}}", value)
        return query
    
    def to_google_url(self, **kwargs) -> str:
        """Generate a Google search URL for this dork."""
        query = self.build(**kwargs)
        encoded = quote_plus(query)
        return f"https://www.google.com/search?q={encoded}"


@dataclass
class DiscoveredDomain:
    """Represents a discovered domain from dork results."""
    domain: str
    source_query: str
    discovered_at: datetime
    url: str
    title: str = ""
    snippet: str = ""
    category: str = ""
    
    def to_dict(self) -> dict:
        return {
            **asdict(self),
            'discovered_at': self.discovered_at.isoformat()
        }


# =============================================================================
# DORK TEMPLATES BY CATEGORY
# =============================================================================

CAREERS_DORKS = [
    DorkTemplate(
        name="careers_url",
        category="careers",
        template='site:*.com inurl:careers "{role}" {exclusions}',
        description="Find /careers pages with role mentions",
        use_case="Daily discovery of career pages",
        priority=1
    ),
    DorkTemplate(
        name="jobs_url",
        category="careers",
        template='site:*.com inurl:jobs "{role}" -site:linkedin.com -site:indeed.com {exclusions}',
        description="Find /jobs pages excluding major boards",
        use_case="Alternative career page paths",
        priority=1
    ),
    DorkTemplate(
        name="careers_title",
        category="careers",
        template='intitle:"careers" "join our team" "{role}" {exclusions}',
        description="Match career page titles with hiring language",
        use_case="Broad discovery",
        priority=2
    ),
    DorkTemplate(
        name="startup_careers",
        category="careers",
        template='site:*.io inurl:careers "{role}" {exclusions}',
        description="Target startup domains (.io TLD)",
        use_case="Startup-focused search",
        priority=1
    ),
    DorkTemplate(
        name="ai_company_careers",
        category="careers",
        template='site:*.ai inurl:careers "{role}" {exclusions}',
        description="Target AI company domains",
        use_case="AI/ML company discovery",
        priority=1
    ),
    DorkTemplate(
        name="apply_now",
        category="careers",
        template='inurl:/careers/ "apply now" "{role}" {exclusions}',
        description="Active hiring pages with CTAs",
        use_case="High-intent leads",
        priority=1
    ),
    DorkTemplate(
        name="work_with_us",
        category="careers",
        template='"work with us" OR "join us" inurl:about "{role}" {exclusions}',
        description="About pages with hiring sections",
        use_case="Smaller companies",
        priority=2
    ),
    DorkTemplate(
        name="open_positions",
        category="careers",
        template='"open positions" "{role}" site:*.com {exclusions}',
        description="Direct open positions language",
        use_case="Active job listings",
        priority=1
    ),
]

HIRING_SIGNAL_DORKS = [
    DorkTemplate(
        name="were_hiring",
        category="hiring_signals",
        template='"we\'re hiring" "{role}" site:*.com {exclusions}',
        description="Direct hiring announcements",
        use_case="High-intent discovery",
        priority=1
    ),
    DorkTemplate(
        name="growing_team",
        category="hiring_signals",
        template='"growing team" "{tech}" -jobs -careers site:*.com {exclusions}',
        description="Growth language without formal pages",
        use_case="Early-stage companies",
        priority=2
    ),
    DorkTemplate(
        name="join_engineering",
        category="hiring_signals",
        template='"join our engineering team" "{tech}" {exclusions}',
        description="Team-specific hiring",
        use_case="Engineering teams",
        priority=1
    ),
    DorkTemplate(
        name="now_hiring",
        category="hiring_signals",
        template='"now hiring" "{location}" "{role}" {exclusions}',
        description="Active hiring with location",
        use_case="Location-specific",
        priority=1
    ),
    DorkTemplate(
        name="expanding_team",
        category="hiring_signals",
        template='"expanding our" "{role}" team {exclusions}',
        description="Expansion language",
        use_case="Growth companies",
        priority=2
    ),
    DorkTemplate(
        name="looking_for",
        category="hiring_signals",
        template='"looking for" "senior" "{role}" site:*.com {exclusions}',
        description="Informal hiring posts",
        use_case="Blog/about pages",
        priority=2
    ),
    DorkTemplate(
        name="come_build",
        category="hiring_signals",
        template='"come build with us" OR "help us build" "{tech}" {exclusions}',
        description="Startup hiring language",
        use_case="Early-stage startups",
        priority=2
    ),
    DorkTemplate(
        name="multiple_positions",
        category="hiring_signals",
        template='"hiring for" "multiple positions" "{role}" {exclusions}',
        description="Bulk hiring signals",
        use_case="Scaling companies",
        priority=1
    ),
]

TECH_STACK_DORKS = [
    DorkTemplate(
        name="we_use",
        category="tech_stack",
        template='"we use" "{tech}" site:*.com careers OR hiring {exclusions}',
        description="Tech stack disclosure with hiring",
        use_case="Stack matching",
        priority=1
    ),
    DorkTemplate(
        name="built_with",
        category="tech_stack",
        template='"built with" "{tech}" careers {exclusions}',
        description="Infrastructure mentions",
        use_case="DevOps/Platform roles",
        priority=2
    ),
    DorkTemplate(
        name="our_stack",
        category="tech_stack",
        template='"our stack" "{tech}" site:*.com {exclusions}',
        description="Explicit stack pages",
        use_case="Tech-focused companies",
        priority=1
    ),
    DorkTemplate(
        name="tech_stack_page",
        category="tech_stack",
        template='"tech stack" "{tech}" careers OR jobs {exclusions}',
        description="Tech stack pages with hiring",
        use_case="ML/AI roles",
        priority=1
    ),
    DorkTemplate(
        name="engineering_blog",
        category="tech_stack",
        template='inurl:engineering "{tech}" "team" site:*.com {exclusions}',
        description="Engineering blogs with tech",
        use_case="Data engineering",
        priority=2
    ),
    DorkTemplate(
        name="powered_by",
        category="tech_stack",
        template='"powered by" "{tech}" careers {exclusions}',
        description="Platform mentions",
        use_case="Data roles",
        priority=2
    ),
]

FUNDING_GROWTH_DORKS = [
    DorkTemplate(
        name="series_a_hiring",
        category="funding",
        template='"series a" "hiring" "{role}" {year} {exclusions}',
        description="Recent Series A + hiring",
        use_case="Post-funding surge",
        priority=1
    ),
    DorkTemplate(
        name="series_b_hiring",
        category="funding",
        template='"series b" "hiring" "{role}" {year} {exclusions}',
        description="Series B + hiring",
        use_case="Growth stage",
        priority=1
    ),
    DorkTemplate(
        name="raised_funding",
        category="funding",
        template='"raised" "$" "million" "team" "{role}" site:*.com {exclusions}',
        description="Funding announcements",
        use_case="Growth companies",
        priority=1
    ),
    DorkTemplate(
        name="vc_backed",
        category="funding",
        template='"backed by" ("sequoia" OR "a16z" OR "accel") careers {exclusions}',
        description="VC-backed companies",
        use_case="Well-funded startups",
        priority=1
    ),
    DorkTemplate(
        name="yc_companies",
        category="funding",
        template='"y combinator" "hiring" "{role}" {exclusions}',
        description="YC companies",
        use_case="Startup ecosystem",
        priority=1
    ),
    DorkTemplate(
        name="seed_round",
        category="funding",
        template='"seed round" "growing" "{role}" {exclusions}',
        description="Early-stage funded",
        use_case="Early opportunities",
        priority=2
    ),
    DorkTemplate(
        name="scaling_team",
        category="funding",
        template='"scaling" "engineering team" "{role}" {exclusions}',
        description="Scaling signals",
        use_case="Growth companies",
        priority=1
    ),
]

REMOTE_DORKS = [
    DorkTemplate(
        name="remote_first",
        category="remote",
        template='"remote-first" "{role}" careers {exclusions}',
        description="Remote-first culture",
        use_case="Remote priority",
        priority=1
    ),
    DorkTemplate(
        name="fully_remote",
        category="remote",
        template='"fully remote" "{role}" "hiring" {exclusions}',
        description="100% remote positions",
        use_case="Remote-only search",
        priority=1
    ),
    DorkTemplate(
        name="distributed_team",
        category="remote",
        template='"distributed team" "{tech}" careers {exclusions}',
        description="Distributed companies",
        use_case="Remote culture",
        priority=1
    ),
    DorkTemplate(
        name="work_anywhere",
        category="remote",
        template='"work from anywhere" "{role}" {exclusions}',
        description="Location-flexible",
        use_case="Global remote",
        priority=1
    ),
    DorkTemplate(
        name="async_remote",
        category="remote",
        template='"async" "remote" "{role}" hiring {exclusions}',
        description="Async-first remote",
        use_case="Time-zone flexible",
        priority=2
    ),
]

ALL_DORKS = {
    'careers': CAREERS_DORKS,
    'hiring_signals': HIRING_SIGNAL_DORKS,
    'tech_stack': TECH_STACK_DORKS,
    'funding': FUNDING_GROWTH_DORKS,
    'remote': REMOTE_DORKS,
}


# =============================================================================
# DORK ENGINE
# =============================================================================

class DorkEngine:
    """
    Engine for generating and managing Google dork queries.
    
    Handles:
    - Query generation from templates
    - Variable substitution (roles, tech, location)
    - Exclusion management
    - Deduplication
    - Output formatting
    """
    
    # Standard exclusions to add to all queries
    STANDARD_EXCLUSIONS = (
        '-site:linkedin.com -site:indeed.com -site:glassdoor.com '
        '-site:ziprecruiter.com -site:monster.com -site:dice.com '
        '-staffing -"recruitment agency"'
    )
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.seen_domains: Set[str] = set()
        self.discoveries: List[DiscoveredDomain] = []
        self._load_blocklist()
        
    def _load_config(self, config_path: Optional[Path]) -> dict:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = PROJECT_ROOT / 'config' / 'config.yaml'
        
        if not config_path.exists():
            config_path = PROJECT_ROOT / 'config' / 'config.example.yaml'
            
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {}
    
    def _load_blocklist(self):
        """Load domain blocklist."""
        blocklist_path = PROJECT_ROOT / 'config' / 'blocklist.yaml'
        self.blocklist = set()
        
        if blocklist_path.exists():
            with open(blocklist_path) as f:
                data = yaml.safe_load(f)
                for category in data.values():
                    if isinstance(category, list):
                        self.blocklist.update(category)
    
    def get_roles(self) -> List[str]:
        """Get target roles from config."""
        return self.config.get('profile', {}).get('target_roles', [
            'data engineer',
            'backend engineer',
            'ml engineer',
            'python developer'
        ])
    
    def get_techs(self) -> List[str]:
        """Get target technologies from config."""
        keywords_path = PROJECT_ROOT / 'config' / 'keywords.yaml'
        techs = ['python', 'spark', 'airflow', 'kubernetes']
        
        if keywords_path.exists():
            with open(keywords_path) as f:
                data = yaml.safe_load(f)
                # Extract high-weight techs
                for category in ['languages', 'data_ml', 'infrastructure']:
                    if category in data:
                        for tech, info in data[category].items():
                            if info.get('weight', 0) >= 0.8:
                                techs.append(tech)
        return list(set(techs))
    
    def get_locations(self) -> List[str]:
        """Get target locations from config."""
        return self.config.get('profile', {}).get('locations', {}).get('preferred', [
            'remote',
            'san francisco',
            'new york'
        ])
    
    def generate_queries(
        self,
        categories: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        techs: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        priority_max: int = 2
    ) -> List[Dict]:
        """
        Generate dork queries from templates.
        
        Args:
            categories: List of dork categories to use (None = all)
            roles: Target roles to search for
            techs: Target technologies
            locations: Target locations
            priority_max: Maximum priority level to include (1=high only, 2=+medium, 3=all)
            
        Returns:
            List of dicts with query info
        """
        if categories is None:
            categories = list(ALL_DORKS.keys())
        if roles is None:
            roles = self.get_roles()
        if techs is None:
            techs = self.get_techs()
        if locations is None:
            locations = self.get_locations()
            
        queries = []
        year = str(datetime.now().year)
        
        for category in categories:
            dorks = ALL_DORKS.get(category, [])
            
            for dork in dorks:
                if dork.priority > priority_max:
                    continue
                    
                # Generate variations based on template variables
                if '{role}' in dork.template:
                    for role in roles[:3]:  # Limit to top 3 roles
                        query = dork.build(
                            role=role,
                            tech=techs[0] if techs else 'python',
                            location=locations[0] if locations else 'remote',
                            year=year,
                            exclusions=self.STANDARD_EXCLUSIONS
                        )
                        queries.append({
                            'name': f"{dork.name}_{role.replace(' ', '_')}",
                            'category': category,
                            'query': query,
                            'google_url': dork.to_google_url(
                                role=role,
                                tech=techs[0] if techs else 'python',
                                location=locations[0] if locations else 'remote',
                                year=year,
                                exclusions=self.STANDARD_EXCLUSIONS
                            ),
                            'description': dork.description,
                            'priority': dork.priority
                        })
                        
                elif '{tech}' in dork.template:
                    for tech in techs[:3]:  # Limit to top 3 techs
                        query = dork.build(
                            tech=tech,
                            role=roles[0] if roles else 'engineer',
                            location=locations[0] if locations else 'remote',
                            year=year,
                            exclusions=self.STANDARD_EXCLUSIONS
                        )
                        queries.append({
                            'name': f"{dork.name}_{tech}",
                            'category': category,
                            'query': query,
                            'google_url': dork.to_google_url(
                                tech=tech,
                                role=roles[0] if roles else 'engineer',
                                location=locations[0] if locations else 'remote',
                                year=year,
                                exclusions=self.STANDARD_EXCLUSIONS
                            ),
                            'description': dork.description,
                            'priority': dork.priority
                        })
                else:
                    query = dork.build(
                        role=roles[0] if roles else 'engineer',
                        tech=techs[0] if techs else 'python',
                        location=locations[0] if locations else 'remote',
                        year=year,
                        exclusions=self.STANDARD_EXCLUSIONS
                    )
                    queries.append({
                        'name': dork.name,
                        'category': category,
                        'query': query,
                        'google_url': dork.to_google_url(
                            role=roles[0] if roles else 'engineer',
                            tech=techs[0] if techs else 'python',
                            location=locations[0] if locations else 'remote',
                            year=year,
                            exclusions=self.STANDARD_EXCLUSIONS
                        ),
                        'description': dork.description,
                        'priority': dork.priority
                    })
        
        return queries
    
    def extract_domain(self, url: str) -> str:
        """Extract root domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return ""
    
    def is_blocked(self, domain: str) -> bool:
        """Check if domain is in blocklist."""
        if not domain:
            return True
        for blocked in self.blocklist:
            if blocked in domain or domain.endswith(blocked):
                return True
        return False
    
    def is_duplicate(self, domain: str) -> bool:
        """Check if domain was already discovered."""
        return domain in self.seen_domains
    
    def add_discovery(
        self,
        url: str,
        query: str,
        title: str = "",
        snippet: str = "",
        category: str = ""
    ) -> Optional[DiscoveredDomain]:
        """
        Add a discovered URL if it passes filters.
        
        Returns:
            DiscoveredDomain if added, None if filtered out
        """
        domain = self.extract_domain(url)
        
        if self.is_blocked(domain):
            return None
        if self.is_duplicate(domain):
            return None
            
        discovery = DiscoveredDomain(
            domain=domain,
            source_query=query,
            discovered_at=datetime.now(),
            url=url,
            title=title,
            snippet=snippet,
            category=category
        )
        
        self.seen_domains.add(domain)
        self.discoveries.append(discovery)
        return discovery
    
    def export_queries_table(self, queries: List[Dict]) -> None:
        """Display queries in a formatted table."""
        table = Table(title="Generated Dork Queries")
        table.add_column("Category", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Priority", style="yellow")
        table.add_column("Query", style="white", max_width=60)
        
        for q in queries:
            table.add_row(
                q['category'],
                q['name'],
                str(q['priority']),
                q['query'][:60] + "..." if len(q['query']) > 60 else q['query']
            )
        
        console.print(table)
    
    def export_urls(self, queries: List[Dict], output_path: Path) -> None:
        """Export Google search URLs to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for q in queries:
                f.write(f"# {q['name']} ({q['category']})\n")
                f.write(f"{q['google_url']}\n\n")
        
        console.print(f"[green]Exported {len(queries)} URLs to {output_path}[/green]")
    
    def export_csv(self, queries: List[Dict], output_path: Path) -> None:
        """Export queries to CSV."""
        import csv
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'category', 'priority', 'query', 'google_url', 'description'])
            writer.writeheader()
            writer.writerows(queries)
        
        console.print(f"[green]Exported {len(queries)} queries to {output_path}[/green]")
    
    def export_discoveries_csv(self, output_path: Path) -> None:
        """Export discovered domains to CSV."""
        import csv
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['domain', 'url', 'title', 'snippet', 'category', 'source_query', 'discovered_at']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for d in self.discoveries:
                writer.writerow(d.to_dict())
        
        console.print(f"[green]Exported {len(self.discoveries)} discoveries to {output_path}[/green]")


# =============================================================================
# CLI INTERFACE
# =============================================================================

@click.command()
@click.option('--category', '-c', multiple=True, help='Dork categories to use')
@click.option('--all-categories', '-a', is_flag=True, help='Use all categories')
@click.option('--priority', '-p', default=2, help='Max priority level (1-3)')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['table', 'urls', 'csv', 'json']), default='table')
@click.option('--role', '-r', multiple=True, help='Target roles')
@click.option('--tech', '-t', multiple=True, help='Target technologies')
def main(category, all_categories, priority, output, format, role, tech):
    """
    Generate Google dork queries for hidden job market discovery.
    
    Examples:
        python dork_engine.py --all-categories --format urls -o queries.txt
        python dork_engine.py -c careers -c hiring_signals --format csv
        python dork_engine.py -r "data engineer" -t spark --format table
    """
    engine = DorkEngine()
    
    # Determine categories
    categories = None
    if all_categories:
        categories = list(ALL_DORKS.keys())
    elif category:
        categories = list(category)
    
    # Generate queries
    queries = engine.generate_queries(
        categories=categories,
        roles=list(role) if role else None,
        techs=list(tech) if tech else None,
        priority_max=priority
    )
    
    console.print(f"\n[bold]Generated {len(queries)} dork queries[/bold]\n")
    
    # Output based on format
    if format == 'table':
        engine.export_queries_table(queries)
    elif format == 'urls':
        output_path = Path(output) if output else PROJECT_ROOT / 'output' / 'dork_urls.txt'
        engine.export_urls(queries, output_path)
    elif format == 'csv':
        output_path = Path(output) if output else PROJECT_ROOT / 'output' / 'dork_queries.csv'
        engine.export_csv(queries, output_path)
    elif format == 'json':
        output_path = Path(output) if output else PROJECT_ROOT / 'output' / 'dork_queries.json'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(queries, f, indent=2)
        console.print(f"[green]Exported to {output_path}[/green]")
    
    # Print usage instructions
    console.print("\n[bold cyan]Next Steps:[/bold cyan]")
    console.print("1. Open the Google URLs in your browser (with delays)")
    console.print("2. Copy relevant company URLs from results")
    console.print("3. Run the scraper: python src/extraction/scraper.py --input domains.txt")


if __name__ == '__main__':
    main()
