#!/usr/bin/env python3
"""
Hidden Job Market Intelligence System - Main Entry Point

Unified CLI for running all system components.

Usage:
    python run.py discover --all
    python run.py scrape --input domains.txt
    python run.py score --priority high
    python run.py detect-changes
    python run.py stats
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """Hidden Job Market Intelligence System
    
    Discover companies before roles appear on job boards.
    """
    pass


@cli.command()
@click.option('--category', '-c', multiple=True, help='Dork categories (careers, hiring_signals, tech_stack, funding, remote)')
@click.option('--all', '-a', 'all_categories', is_flag=True, help='Use all categories')
@click.option('--format', '-f', type=click.Choice(['table', 'urls', 'csv']), default='urls')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
def discover(category, all_categories, format, output):
    """Generate Google dork queries for discovery."""
    from src.discovery.dork_engine import DorkEngine, ALL_DORKS
    
    engine = DorkEngine()
    
    categories = list(ALL_DORKS.keys()) if all_categories else (list(category) if category else None)
    queries = engine.generate_queries(categories=categories)
    
    console.print(f"\n[bold]Generated {len(queries)} dork queries[/bold]\n")
    
    if format == 'table':
        engine.export_queries_table(queries)
    elif format == 'urls':
        output_path = Path(output) if output else PROJECT_ROOT / 'output' / 'dork_urls.txt'
        engine.export_urls(queries, output_path)
    elif format == 'csv':
        output_path = Path(output) if output else PROJECT_ROOT / 'output' / 'dork_queries.csv'
        engine.export_csv(queries, output_path)
    
    console.print("\n[cyan]Next: Open URLs in browser, collect domains, then run 'scrape'[/cyan]")


@cli.command()
@click.option('--url', '-u', help='Single URL to scrape')
@click.option('--domain', '-d', help='Single domain to scrape')
@click.option('--input', '-i', 'input_file', type=click.Path(exists=True), help='File with domains')
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--max-pages', '-m', default=5, help='Max pages per domain')
def scrape(url, domain, input_file, output, max_pages):
    """Scrape company websites for job intelligence."""
    from src.extraction.scraper import JobMarketScraper
    
    scraper = JobMarketScraper()
    output_dir = Path(output) if output else PROJECT_ROOT / 'output' / 'scrape_results'
    
    if url:
        console.print(f"[cyan]Scraping URL: {url}[/cyan]")
        page = scraper.scrape_page(url)
        if page:
            console.print(f"[green]Success![/green]")
            console.print(f"  Title: {page.title}")
            console.print(f"  Type: {page.page_type}")
            console.print(f"  Jobs: {page.job_titles}")
            console.print(f"  Tech: {page.tech_keywords}")
    
    elif domain:
        console.print(f"[cyan]Scraping domain: {domain}[/cyan]")
        profile = scraper.scrape_domain(domain, max_pages)
        scraper.export_profiles_csv(output_dir / 'profiles.csv')
        scraper.export_pages_csv(output_dir / 'pages.csv')
    
    elif input_file:
        with open(input_file) as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        console.print(f"[cyan]Scraping {len(domains)} domains...[/cyan]")
        scraper.scrape_domains(domains, max_pages)
        scraper.export_profiles_csv(output_dir / 'profiles.csv')
        scraper.export_pages_csv(output_dir / 'pages.csv')
        console.print(f"\n[green]Complete! Results in {output_dir}[/green]")
    
    else:
        console.print("[red]Please provide --url, --domain, or --input[/red]")
        return
    
    console.print("\n[cyan]Next: Run 'score' to prioritize leads[/cyan]")


@cli.command()
@click.option('--input', '-i', 'input_file', type=click.Path(exists=True), help='Input profiles CSV')
@click.option('--priority', '-p', type=click.Choice(['high', 'medium', 'low']), help='Filter by priority')
@click.option('--limit', '-l', default=50, help='Max leads to show')
@click.option('--output', '-o', type=click.Path(), help='Output CSV path')
def score(input_file, priority, limit, output):
    """Score and prioritize leads."""
    from src.scoring.scorer import LeadScorer, load_companies_from_csv
    from datetime import datetime
    
    # Find input file
    if not input_file:
        default_input = PROJECT_ROOT / 'output' / 'scrape_results' / 'profiles.csv'
        if default_input.exists():
            input_file = str(default_input)
        else:
            console.print("[red]No profiles.csv found. Run 'scrape' first.[/red]")
            return
    
    console.print(f"[cyan]Loading from {input_file}...[/cyan]")
    companies = load_companies_from_csv(Path(input_file))
    
    scorer = LeadScorer()
    scores = scorer.score_companies(companies)
    
    if priority:
        scores = scorer.filter_leads(scores, priority=priority)
    
    scorer.display_scores(scores, limit=limit)
    
    # Summary
    high = len([s for s in scores if s.priority == 'high'])
    med = len([s for s in scores if s.priority == 'medium'])
    
    console.print(f"\n[bold]Summary:[/bold] {high} high, {med} medium priority leads")
    
    # Export
    output_path = Path(output) if output else PROJECT_ROOT / 'output' / 'reports' / f'scored_leads_{datetime.now().strftime("%Y%m%d")}.csv'
    scorer.export_csv(scores[:limit], output_path)


@cli.command('detect-changes')
@click.option('--domains', '-d', type=click.Path(exists=True), help='File with domains to check')
@click.option('--all-high', is_flag=True, help='Check all high-priority leads')
def detect_changes(domains, all_high):
    """Detect changes on monitored companies."""
    from src.extraction.change_detector import ChangeDetector
    from datetime import datetime
    
    detector = ChangeDetector()
    
    if all_high:
        scores = detector.db.get_latest_scores(priority='high')
        domain_list = [s['domain'] for s in scores]
    elif domains:
        with open(domains) as f:
            domain_list = [line.strip() for line in f if line.strip()]
    else:
        console.print("[red]Please provide --domains or --all-high[/red]")
        return
    
    console.print(f"[cyan]Checking {len(domain_list)} domains...[/cyan]")
    changes = detector.run_detection(domain_list)
    detector.display_changes(changes)
    
    output_path = PROJECT_ROOT / 'output' / 'alerts' / f'changes_{datetime.now().strftime("%Y%m%d")}.json'
    detector.export_changes(output_path)


@cli.command()
def stats():
    """Show database statistics."""
    from src.utils.database import LeadDatabase
    
    db = LeadDatabase()
    stats = db.get_stats()
    
    console.print(Panel.fit(
        f"""[bold]Database Statistics[/bold]

[cyan]Domains:[/cyan]
  Pending: {stats.get('domains_by_status', {}).get('pending', 0)}
  Scraped: {stats.get('domains_by_status', {}).get('scraped', 0)}
  Blocked: {stats.get('domains_by_status', {}).get('blocked', 0)}

[cyan]Data:[/cyan]
  Total Pages: {stats.get('total_pages', 0)}
  Total Companies: {stats.get('total_companies', 0)}

[cyan]Leads by Priority:[/cyan]
  High: {stats.get('scores_by_priority', {}).get('high', 0)}
  Medium: {stats.get('scores_by_priority', {}).get('medium', 0)}
  Low: {stats.get('scores_by_priority', {}).get('low', 0)}

[cyan]Activity:[/cyan]
  Changes (7 days): {stats.get('changes_last_7_days', 0)}
""",
        title="Hidden Job Market Intelligence"
    ))


@cli.command()
def init():
    """Initialize project directories and copy example config."""
    import shutil
    
    # Create directories
    dirs = [
        'data/raw',
        'data/processed',
        'output/reports',
        'output/scrape_results',
        'output/alerts'
    ]
    
    for d in dirs:
        path = PROJECT_ROOT / d
        path.mkdir(parents=True, exist_ok=True)
        console.print(f"[green]✓[/green] Created {d}/")
    
    # Copy config if needed
    config_path = PROJECT_ROOT / 'config' / 'config.yaml'
    example_path = PROJECT_ROOT / 'config' / 'config.example.yaml'
    
    if not config_path.exists() and example_path.exists():
        shutil.copy(example_path, config_path)
        console.print(f"[green]✓[/green] Created config/config.yaml from example")
    
    console.print("\n[bold green]Project initialized![/bold green]")
    console.print("\nNext steps:")
    console.print("  1. Edit config/config.yaml with your preferences")
    console.print("  2. Run: python run.py discover --all")


if __name__ == '__main__':
    cli()
