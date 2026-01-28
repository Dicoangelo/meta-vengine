#!/usr/bin/env python3
"""
Real-time Cost Alert System

Monitors spending and sends alerts when thresholds are exceeded.
Can integrate with:
- Desktop notifications (macOS)
- Webhook (Slack, Discord, etc.)
- Log file alerts

Run via daemon or cron.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home()
CONFIG_FILE = HOME / ".claude/config/system.json"
COST_FILE = HOME / ".claude/kernel/cost-data.json"
ALERT_LOG = HOME / ".claude/logs/cost-alerts.log"
ALERT_STATE = HOME / ".claude/data/.last-cost-alert"

# Default thresholds
DEFAULT_DAILY_ALERT = 250
DEFAULT_WEEKLY_ALERT = 1500

def load_config():
    """Load alert thresholds from config."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            return config.get("alerts", {})
        except:
            pass
    return {}

def load_cost_data():
    """Load current cost data."""
    if COST_FILE.exists():
        try:
            with open(COST_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

def send_notification(title: str, message: str):
    """Send macOS notification."""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{message}" with title "{title}"'
        ], capture_output=True, timeout=5)
        return True
    except:
        return False

def log_alert(level: str, message: str):
    """Log alert to file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {message}"
    print(line)
    try:
        ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERT_LOG, "a") as f:
            f.write(line + "\n")
    except:
        pass

def check_already_alerted(alert_key: str) -> bool:
    """Check if we already sent this alert today."""
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{today}:{alert_key}"

    if ALERT_STATE.exists():
        try:
            alerts = ALERT_STATE.read_text().strip().split("\n")
            return key in alerts
        except:
            pass
    return False

def mark_alerted(alert_key: str):
    """Mark alert as sent."""
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{today}:{alert_key}"

    try:
        ALERT_STATE.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERT_STATE, "a") as f:
            f.write(key + "\n")
    except:
        pass

def check_alerts():
    """Check all alert conditions."""
    config = load_config()
    cost_data = load_cost_data()

    daily_threshold = config.get("dailySpendAlert", DEFAULT_DAILY_ALERT)
    weekly_threshold = config.get("weeklySpendAlert", DEFAULT_WEEKLY_ALERT)
    cache_threshold = config.get("cacheEfficiencyAlert", 75)

    today_cost = cost_data.get("today", 0)
    week_cost = cost_data.get("thisWeek", 0)
    cache_eff = cost_data.get("cacheEfficiency", 100)

    alerts_sent = 0

    # Daily spend alert
    if today_cost > daily_threshold:
        if not check_already_alerted("daily_spend"):
            msg = f"Daily spend ${today_cost:.2f} exceeds ${daily_threshold}"
            log_alert("WARN", msg)
            send_notification("💰 CCC Cost Alert", msg)
            mark_alerted("daily_spend")
            alerts_sent += 1

    # Weekly spend alert
    if week_cost > weekly_threshold:
        if not check_already_alerted("weekly_spend"):
            msg = f"Weekly spend ${week_cost:.2f} exceeds ${weekly_threshold}"
            log_alert("WARN", msg)
            send_notification("💰 CCC Weekly Alert", msg)
            mark_alerted("weekly_spend")
            alerts_sent += 1

    # Cache efficiency alert
    if cache_eff < cache_threshold:
        if not check_already_alerted("cache_efficiency"):
            msg = f"Cache efficiency {cache_eff}% below {cache_threshold}%"
            log_alert("WARN", msg)
            send_notification("⚠️ CCC Cache Alert", msg)
            mark_alerted("cache_efficiency")
            alerts_sent += 1

    return alerts_sent

def main():
    if "--check" in sys.argv or len(sys.argv) == 1:
        alerts = check_alerts()
        if alerts:
            print(f"Sent {alerts} alert(s)")
        else:
            print("All metrics within thresholds")
    elif "--status" in sys.argv:
        cost_data = load_cost_data()
        config = load_config()
        print(f"Today: ${cost_data.get('today', 0):.2f} (alert: ${config.get('dailySpendAlert', DEFAULT_DAILY_ALERT)})")
        print(f"Week: ${cost_data.get('thisWeek', 0):.2f}")
        print(f"Cache: {cost_data.get('cacheEfficiency', 0)}%")
    elif "--test" in sys.argv:
        send_notification("🧪 CCC Test Alert", "This is a test notification")
        print("Test notification sent")
    else:
        print("Usage: cost-alert.py [--check|--status|--test]")

if __name__ == "__main__":
    main()
