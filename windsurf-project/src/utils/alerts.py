"""
Alert System for Job Market Intelligence

Optional module for sending notifications when:
- High-priority leads are discovered
- Changes detected on monitored companies
- New job listings match criteria

Supports:
- Slack webhooks
- Discord webhooks
- Email (SMTP)
- Desktop notifications (Windows/Mac)
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests

import yaml


PROJECT_ROOT = Path(__file__).parent.parent.parent


@dataclass
class Alert:
    """Represents an alert to be sent."""
    title: str
    message: str
    priority: str  # high, medium, low
    data: Dict = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AlertManager:
    """
    Manages alert delivery across multiple channels.
    
    Configuration in config.yaml:
    ```yaml
    output:
      alerts:
        enabled: true
        slack_webhook: "https://hooks.slack.com/..."
        discord_webhook: "https://discord.com/api/webhooks/..."
        email:
          smtp_host: "smtp.gmail.com"
          smtp_port: 587
          username: "your@email.com"
          password: "app_password"
          to: "alerts@email.com"
    ```
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self.enabled = self.config.get('enabled', False)
    
    def _load_config(self, config_path: Optional[Path]) -> dict:
        """Load alert configuration."""
        if config_path is None:
            config_path = PROJECT_ROOT / 'config' / 'config.yaml'
        
        if config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f)
                return data.get('output', {}).get('alerts', {})
        return {}
    
    def send(self, alert: Alert) -> bool:
        """Send alert to all configured channels."""
        if not self.enabled:
            return False
        
        success = False
        
        # Slack
        if self.config.get('slack_webhook'):
            if self._send_slack(alert):
                success = True
        
        # Discord
        if self.config.get('discord_webhook'):
            if self._send_discord(alert):
                success = True
        
        # Email
        if self.config.get('email', {}).get('smtp_host'):
            if self._send_email(alert):
                success = True
        
        return success
    
    def _send_slack(self, alert: Alert) -> bool:
        """Send alert to Slack webhook."""
        webhook_url = self.config.get('slack_webhook')
        if not webhook_url:
            return False
        
        # Format message
        color = {
            'high': '#ff0000',
            'medium': '#ffaa00',
            'low': '#00aa00'
        }.get(alert.priority, '#808080')
        
        payload = {
            'attachments': [{
                'color': color,
                'title': alert.title,
                'text': alert.message,
                'footer': f"Hidden Job Market | {alert.timestamp.strftime('%Y-%m-%d %H:%M')}",
                'fields': []
            }]
        }
        
        # Add data fields
        if alert.data:
            for key, value in alert.data.items():
                payload['attachments'][0]['fields'].append({
                    'title': key,
                    'value': str(value),
                    'short': True
                })
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def _send_discord(self, alert: Alert) -> bool:
        """Send alert to Discord webhook."""
        webhook_url = self.config.get('discord_webhook')
        if not webhook_url:
            return False
        
        color = {
            'high': 0xff0000,
            'medium': 0xffaa00,
            'low': 0x00aa00
        }.get(alert.priority, 0x808080)
        
        payload = {
            'embeds': [{
                'title': alert.title,
                'description': alert.message,
                'color': color,
                'timestamp': alert.timestamp.isoformat(),
                'footer': {'text': 'Hidden Job Market Intelligence'}
            }]
        }
        
        # Add data fields
        if alert.data:
            payload['embeds'][0]['fields'] = [
                {'name': k, 'value': str(v), 'inline': True}
                for k, v in alert.data.items()
            ]
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            return response.status_code in (200, 204)
        except requests.RequestException:
            return False
    
    def _send_email(self, alert: Alert) -> bool:
        """Send alert via email."""
        email_config = self.config.get('email', {})
        
        if not all([
            email_config.get('smtp_host'),
            email_config.get('username'),
            email_config.get('to')
        ]):
            return False
        
        msg = MIMEMultipart()
        msg['From'] = email_config['username']
        msg['To'] = email_config['to']
        msg['Subject'] = f"[{alert.priority.upper()}] {alert.title}"
        
        # Build body
        body = f"{alert.message}\n\n"
        if alert.data:
            body += "Details:\n"
            for key, value in alert.data.items():
                body += f"  - {key}: {value}\n"
        body += f"\nTimestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            server = smtplib.SMTP(
                email_config['smtp_host'],
                email_config.get('smtp_port', 587)
            )
            server.starttls()
            server.login(
                email_config['username'],
                email_config.get('password', '')
            )
            server.send_message(msg)
            server.quit()
            return True
        except Exception:
            return False
    
    # Convenience methods for common alerts
    
    def alert_high_priority_lead(self, domain: str, score: float, roles: List[str]):
        """Send alert for new high-priority lead."""
        alert = Alert(
            title=f"🎯 High-Priority Lead: {domain}",
            message=f"New high-scoring company discovered with matching roles.",
            priority='high',
            data={
                'Domain': domain,
                'Score': f"{score:.1f}/100",
                'Roles': ', '.join(roles[:3])
            }
        )
        return self.send(alert)
    
    def alert_new_listing(self, domain: str, job_title: str):
        """Send alert for new job listing."""
        alert = Alert(
            title=f"📋 New Listing: {domain}",
            message=f"New job posting detected: {job_title}",
            priority='medium',
            data={
                'Domain': domain,
                'Position': job_title
            }
        )
        return self.send(alert)
    
    def alert_score_change(self, domain: str, old_score: float, new_score: float):
        """Send alert for significant score change."""
        direction = "📈" if new_score > old_score else "📉"
        alert = Alert(
            title=f"{direction} Score Change: {domain}",
            message=f"Lead score changed from {old_score:.1f} to {new_score:.1f}",
            priority='medium' if new_score > old_score else 'low',
            data={
                'Domain': domain,
                'Old Score': f"{old_score:.1f}",
                'New Score': f"{new_score:.1f}",
                'Change': f"{new_score - old_score:+.1f}"
            }
        )
        return self.send(alert)
    
    def alert_daily_summary(self, stats: Dict):
        """Send daily summary alert."""
        alert = Alert(
            title="📊 Daily Summary",
            message="Here's your daily job market intelligence summary.",
            priority='low',
            data=stats
        )
        return self.send(alert)
