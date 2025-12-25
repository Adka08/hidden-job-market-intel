"""
Change Detection Module

Monitors high-priority leads for changes:
- New job listings
- Removed listings
- Content changes on careers pages
- Score changes over time

Usage:
    python change_detector.py --domains high_priority.txt
    python change_detector.py --all-high-priority
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.extraction.scraper import JobMarketScraper, ScrapedPage
from src.utils.database import LeadDatabase

from rich.console import Console
from rich.table import Table
import click

console = Console()


@dataclass
class Change:
    """Represents a detected change."""
    domain: str
    url: str
    change_type: str  # new_listing, removed_listing, content_change, new_signal
    old_value: Optional[str]
    new_value: Optional[str]
    detected_at: datetime
    
    def to_dict(self) -> dict:
        return {
            'domain': self.domain,
            'url': self.url,
            'change_type': self.change_type,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'detected_at': self.detected_at.isoformat()
        }


class ChangeDetector:
    """
    Detects changes in company career pages.
    
    Change Types:
    - new_listing: New job title appeared
    - removed_listing: Job title disappeared
    - content_change: Page content hash changed
    - new_signal: New hiring/funding signal detected
    - score_change: Lead score changed significantly
    """
    
    SIGNIFICANT_SCORE_CHANGE = 10  # Points
    
    def __init__(self, db: Optional[LeadDatabase] = None):
        self.db = db or LeadDatabase()
        self.scraper = JobMarketScraper()
        self.changes: List[Change] = []
    
    def detect_page_changes(self, url: str) -> List[Change]:
        """
        Compare current page state to stored state.
        
        Returns list of detected changes.
        """
        changes = []
        
        # Get stored page data
        stored = self.db.get_page_by_url(url)
        if not stored:
            return changes
        
        # Scrape current state
        current = self.scraper.scrape_page(url)
        if not current:
            return changes
        
        domain = current.domain
        
        # Check content hash
        if stored.get('content_hash') != current.content_hash:
            changes.append(Change(
                domain=domain,
                url=url,
                change_type='content_change',
                old_value=stored.get('content_hash'),
                new_value=current.content_hash,
                detected_at=datetime.now()
            ))
        
        # Check job titles
        old_titles = set(stored.get('job_titles', []))
        new_titles = set(current.job_titles)
        
        added_titles = new_titles - old_titles
        removed_titles = old_titles - new_titles
        
        for title in added_titles:
            changes.append(Change(
                domain=domain,
                url=url,
                change_type='new_listing',
                old_value=None,
                new_value=title,
                detected_at=datetime.now()
            ))
        
        for title in removed_titles:
            changes.append(Change(
                domain=domain,
                url=url,
                change_type='removed_listing',
                old_value=title,
                new_value=None,
                detected_at=datetime.now()
            ))
        
        # Check hiring signals
        old_signals = set(stored.get('hiring_signals', []))
        new_signals = set(current.hiring_signals)
        
        added_signals = new_signals - old_signals
        for signal in added_signals:
            changes.append(Change(
                domain=domain,
                url=url,
                change_type='new_signal',
                old_value=None,
                new_value=signal,
                detected_at=datetime.now()
            ))
        
        return changes
    
    def detect_domain_changes(self, domain: str) -> List[Change]:
        """Detect changes for all pages of a domain."""
        changes = []
        
        # Get company data
        company = self.db.get_company(domain)
        if not company:
            return changes
        
        # Check careers URL if available
        if company.get('careers_url'):
            page_changes = self.detect_page_changes(company['careers_url'])
            changes.extend(page_changes)
        
        return changes
    
    def detect_score_changes(self, domain: str) -> Optional[Change]:
        """Check if score changed significantly."""
        history = self.db.get_score_history(domain)
        
        if len(history) < 2:
            return None
        
        latest = history[0]
        previous = history[1]
        
        score_diff = abs(latest['total_score'] - previous['total_score'])
        
        if score_diff >= self.SIGNIFICANT_SCORE_CHANGE:
            return Change(
                domain=domain,
                url='',
                change_type='score_change',
                old_value=previous['total_score'],
                new_value=latest['total_score'],
                detected_at=datetime.now()
            )
        
        return None
    
    def run_detection(self, domains: List[str]) -> List[Change]:
        """Run change detection on a list of domains."""
        all_changes = []
        
        for domain in domains:
            console.print(f"[cyan]Checking {domain}...[/cyan]")
            
            # Page changes
            domain_changes = self.detect_domain_changes(domain)
            all_changes.extend(domain_changes)
            
            # Score changes
            score_change = self.detect_score_changes(domain)
            if score_change:
                all_changes.append(score_change)
            
            # Log to database
            for change in domain_changes:
                self.db.log_change(
                    domain=change.domain,
                    change_type=change.change_type,
                    old_value=change.old_value,
                    new_value=change.new_value,
                    url=change.url
                )
        
        self.changes = all_changes
        return all_changes
    
    def display_changes(self, changes: List[Change]):
        """Display changes in a formatted table."""
        if not changes:
            console.print("[green]No changes detected.[/green]")
            return
        
        table = Table(title=f"Detected Changes ({len(changes)})")
        table.add_column("Domain", style="cyan")
        table.add_column("Type", style="yellow")
        table.add_column("Old Value", max_width=30)
        table.add_column("New Value", max_width=30)
        
        for change in changes:
            type_color = {
                'new_listing': '[green]',
                'removed_listing': '[red]',
                'content_change': '[yellow]',
                'new_signal': '[green]',
                'score_change': '[magenta]'
            }.get(change.change_type, '')
            
            table.add_row(
                change.domain,
                f"{type_color}{change.change_type}[/]",
                str(change.old_value)[:30] if change.old_value else "-",
                str(change.new_value)[:30] if change.new_value else "-"
            )
        
        console.print(table)
    
    def export_changes(self, output_path: Path):
        """Export changes to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump([c.to_dict() for c in self.changes], f, indent=2)
        
        console.print(f"[green]Exported {len(self.changes)} changes to {output_path}[/green]")


# =============================================================================
# CLI INTERFACE
# =============================================================================

@click.command()
@click.option('--domains', '-d', type=click.Path(exists=True), help='File with domains to check')
@click.option('--all-high-priority', is_flag=True, help='Check all high-priority leads from database')
@click.option('--output', '-o', type=click.Path(), help='Output JSON path')
def main(domains, all_high_priority, output):
    """
    Detect changes in company career pages.
    
    Examples:
        python change_detector.py --domains high_priority.txt
        python change_detector.py --all-high-priority
    """
    detector = ChangeDetector()
    
    domain_list = []
    
    if all_high_priority:
        # Get high-priority domains from database
        scores = detector.db.get_latest_scores(priority='high')
        domain_list = [s['domain'] for s in scores]
        console.print(f"[cyan]Checking {len(domain_list)} high-priority domains...[/cyan]")
    
    elif domains:
        with open(domains) as f:
            domain_list = [line.strip() for line in f if line.strip()]
        console.print(f"[cyan]Checking {len(domain_list)} domains from file...[/cyan]")
    
    else:
        console.print("[red]Please provide --domains or --all-high-priority[/red]")
        raise click.Abort()
    
    # Run detection
    changes = detector.run_detection(domain_list)
    
    # Display results
    detector.display_changes(changes)
    
    # Export if requested
    if output:
        detector.export_changes(Path(output))
    else:
        output_path = PROJECT_ROOT / 'output' / 'alerts' / f'changes_{datetime.now().strftime("%Y%m%d")}.json'
        detector.export_changes(output_path)
    
    # Summary
    if changes:
        new_listings = len([c for c in changes if c.change_type == 'new_listing'])
        removed = len([c for c in changes if c.change_type == 'removed_listing'])
        
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  [green]New listings:[/green] {new_listings}")
        console.print(f"  [red]Removed listings:[/red] {removed}")
        console.print(f"  [yellow]Other changes:[/yellow] {len(changes) - new_listings - removed}")


if __name__ == '__main__':
    main()
