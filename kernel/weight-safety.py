"""
US-105: Safety Bounds — Drift Detection and Rollback

Prevents weight drift from degrading routing quality via:
- Max drift per epoch (24h): no parameter moves more than 5% from epoch start
- Reward drop rollback: if avg reward drops >8% below 7-day rolling avg, rollback
- Minimum trial threshold: don't trust weights with < 20 trials
- Daily snapshots to data/weight-snapshots/YYYY-MM-DD.json
- Rollback/alert logging to data/weight-rollbacks.jsonl and data/weight-alerts.jsonl
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class WeightSafety:
    """Drift detection, clamping, snapshots, and rollback for learnable weights."""

    DEFAULT_MAX_DRIFT = 0.05       # 5% max drift per epoch
    DEFAULT_REWARD_THRESHOLD = 0.08  # 8% reward drop triggers rollback
    DEFAULT_MIN_TRIALS = 20
    DEFAULT_MAX_SNAPSHOT_AGE = 90   # days

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.snapshot_dir = self.base_dir / "data" / "weight-snapshots"
        self.rollback_log = self.base_dir / "data" / "weight-rollbacks.jsonl"
        self.alert_log = self.base_dir / "data" / "weight-alerts.jsonl"

    # ── Drift Detection ──────────────────────────────────────────────

    def check_drift(
        self,
        current_weights: dict[str, float],
        epoch_start_weights: dict[str, float],
        max_drift: float = DEFAULT_MAX_DRIFT,
    ) -> list[dict[str, Any]]:
        """Return list of violations where a param drifted more than max_drift from epoch start."""
        violations: list[dict[str, Any]] = []
        for param_id, current_val in current_weights.items():
            start_val = epoch_start_weights.get(param_id)
            if start_val is None:
                continue
            if start_val == 0:
                drift = abs(current_val) if current_val != 0 else 0.0
            else:
                drift = abs(current_val - start_val) / abs(start_val)
            if drift > max_drift:
                violations.append({
                    "param_id": param_id,
                    "start": start_val,
                    "current": current_val,
                    "drift": round(drift, 6),
                    "max_drift": max_drift,
                })
        return violations

    def clamp_drift(
        self,
        current_weights: dict[str, float],
        epoch_start_weights: dict[str, float],
        max_drift: float = DEFAULT_MAX_DRIFT,
    ) -> dict[str, float]:
        """Clamp each weight so it stays within max_drift of its epoch start value."""
        clamped: dict[str, float] = {}
        for param_id, current_val in current_weights.items():
            start_val = epoch_start_weights.get(param_id)
            if start_val is None:
                clamped[param_id] = current_val
                continue
            max_abs_drift = abs(start_val) * max_drift
            lo = start_val - max_abs_drift
            hi = start_val + max_abs_drift
            clamped[param_id] = round(max(lo, min(hi, current_val)), 6)
        return clamped

    # ── Reward Drop Detection ────────────────────────────────────────

    def check_reward_drop(
        self,
        current_avg: float,
        rolling_7d_avg: float,
        threshold: float = DEFAULT_REWARD_THRESHOLD,
    ) -> bool:
        """Return True if current_avg dropped more than threshold below rolling_7d_avg."""
        if rolling_7d_avg <= 0:
            return False
        drop = (rolling_7d_avg - current_avg) / rolling_7d_avg
        return drop > threshold

    # ── Snapshots ────────────────────────────────────────────────────

    def take_snapshot(
        self,
        current_weights: dict[str, float],
        bandit_state: dict[str, Any] | None = None,
        avg_reward: float | None = None,
    ) -> str:
        """Write a daily snapshot and return the file path."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        path = self.snapshot_dir / f"{today}.json"

        snapshot = {
            "date": today,
            "timestamp": datetime.now().isoformat(),
            "weights": current_weights,
            "bandit_state": bandit_state or {},
            "avg_reward": avg_reward,
            "promoted": False,
        }
        path.write_text(json.dumps(snapshot, indent=2) + "\n")
        return str(path)

    def get_latest_snapshot(self) -> dict[str, Any] | None:
        """Return the most recent snapshot dict, or None."""
        if not self.snapshot_dir.exists():
            return None
        files = sorted(self.snapshot_dir.glob("*.json"))
        if not files:
            return None
        try:
            return json.loads(files[-1].read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def rollback(self, snapshot_path: str | Path, reason: str) -> dict[str, float]:
        """Restore weights from a snapshot file, log the rollback, return restored weights."""
        snap_path = Path(snapshot_path)
        if not snap_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snap_path}")

        snapshot = json.loads(snap_path.read_text())
        restored = snapshot.get("weights", {})

        self.log_rollback(
            reason=reason,
            pre_weights={},  # caller should supply, but default to empty
            post_weights=restored,
            snapshot_path=str(snap_path),
        )
        return restored

    def prune_snapshots(
        self, max_age_days: int = DEFAULT_MAX_SNAPSHOT_AGE, keep_promoted: bool = True
    ) -> int:
        """Delete snapshots older than max_age_days. Return count deleted."""
        if not self.snapshot_dir.exists():
            return 0

        cutoff = datetime.now() - timedelta(days=max_age_days)
        deleted = 0

        for f in sorted(self.snapshot_dir.glob("*.json")):
            try:
                date_str = f.stem  # YYYY-MM-DD
                snap_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

            if snap_date >= cutoff:
                continue

            if keep_promoted:
                try:
                    data = json.loads(f.read_text())
                    if data.get("promoted", False):
                        continue
                except (json.JSONDecodeError, OSError):
                    pass

            f.unlink()
            deleted += 1

        return deleted

    # ── Logging ──────────────────────────────────────────────────────

    def log_rollback(
        self,
        reason: str,
        pre_weights: dict[str, float],
        post_weights: dict[str, float],
        snapshot_path: str | None = None,
    ) -> None:
        """Append a rollback event to data/weight-rollbacks.jsonl."""
        self.rollback_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "pre_weights": pre_weights,
            "post_weights": post_weights,
            "snapshot_path": snapshot_path,
        }
        with open(self.rollback_log, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_alert(self, alert_type: str, details: dict[str, Any] | None = None) -> None:
        """Append an alert event to data/weight-alerts.jsonl."""
        self.alert_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "alert_type": alert_type,
            "details": details or {},
        }
        with open(self.alert_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
