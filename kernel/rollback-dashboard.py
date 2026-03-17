"""
US-210: Rollback Recovery Dashboard — Data Layer

Reads rollback reports from data/rollback-reports/ and provides
query/summary functions for the dashboard API.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class RollbackDashboard:
    """Query and summarize rollback reports."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.report_dir = self.base_dir / "data" / "rollback-reports"

    def _load_reports(self) -> list[dict[str, Any]]:
        """Load all report JSON files, sorted by timestamp ascending."""
        if not self.report_dir.exists():
            return []
        reports: list[dict[str, Any]] = []
        for f in sorted(self.report_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                data["_file"] = f.name
                reports.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return reports

    def get_rollbacks(
        self,
        last: int | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get rollback reports with optional filters.

        Args:
            last: Return only the N most recent reports.
            severity: Filter by severity ("warning" or "critical").

        Returns:
            List of report dicts, most recent first.
        """
        reports = self._load_reports()

        if severity is not None:
            reports = [r for r in reports if r.get("severity") == severity]

        # Reverse to most-recent-first
        reports = list(reversed(reports))

        if last is not None:
            reports = reports[:last]

        return reports

    def get_rollback_summary(self) -> dict[str, Any]:
        """Return a summary of all rollback reports.

        Returns dict with:
            total: total report count
            by_trigger: count per trigger type
            by_severity: count per severity level
            last_7d: count in last 7 days
            last_30d: count in last 30 days
            latest: most recent report or None
        """
        reports = self._load_reports()
        now = datetime.now()
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)

        by_trigger: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        last_7d = 0
        last_30d = 0

        for r in reports:
            trigger = r.get("trigger", "unknown")
            sev = r.get("severity", "unknown")
            by_trigger[trigger] = by_trigger.get(trigger, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1

            ts_str = r.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts >= cutoff_7d:
                        last_7d += 1
                    if ts >= cutoff_30d:
                        last_30d += 1
                except (ValueError, TypeError):
                    pass

        latest = reports[-1] if reports else None

        return {
            "total": len(reports),
            "by_trigger": by_trigger,
            "by_severity": by_severity,
            "last_7d": last_7d,
            "last_30d": last_30d,
            "latest": latest,
        }


if __name__ == "__main__":
    dashboard = RollbackDashboard()
    summary = dashboard.get_rollback_summary()
    print(json.dumps(summary, indent=2))
