#!/usr/bin/env python3
"""serve.py — HTTP server for the meta-vengine learning-loop dashboard.

Serves static files from kernel/dashboard/ and JSON API endpoints
that read live data from config/ and data/ directories.

Usage:
    python3 kernel/dashboard/serve.py              # default port 8420
    python3 kernel/dashboard/serve.py --port 9000  # custom port
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DASHBOARD_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASHBOARD_DIR.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

LEARNABLE_PARAMS = CONFIG_DIR / "learnable-params.json"
BANDIT_STATE = DATA_DIR / "bandit-state.json"
BANDIT_HISTORY = DATA_DIR / "bandit-history.jsonl"
LRF_CLUSTERS = DATA_DIR / "lrf-clusters.json"
WEIGHT_SNAPSHOTS = DATA_DIR / "weight-snapshots"
DAEMON_HEALTH = PROJECT_ROOT / "kernel" / "daemon-health.py"
ROLLBACK_REPORTS_DIR = DATA_DIR / "rollback-reports"
AB_REPORTS_DIR = DATA_DIR / "ab-reports"

# PCA projection cache: (mtime, result)
_pca_cache: tuple = (0.0, None)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_json(path: Path):
    """Read and parse a JSON file. Returns None if missing."""
    if not path.is_file():
        return None
    with open(path, "r") as fh:
        return json.load(fh)


def read_jsonl_tail(path: Path, n: int = 100):
    """Return the last *n* lines from a JSONL file as a list of dicts."""
    if not path.is_file():
        return []
    lines = []
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if line:
                lines.append(line)
    tail = lines[-n:]
    result = []
    for line in tail:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def get_daemon_health():
    """Run daemon-health.py --json and return parsed output."""
    if not DAEMON_HEALTH.is_file():
        return {"overall": "unknown", "daemons": [], "error": "daemon-health.py not found"}
    try:
        proc = subprocess.run(
            [sys.executable, str(DAEMON_HEALTH), "--json"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        return json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return {"overall": "unknown", "daemons": [], "error": str(exc)}


def build_health_response():
    """Build the /api/health composite response."""
    params_data = read_json(LEARNABLE_PARAMS) or {}
    bandit_data = read_json(BANDIT_STATE) or {}
    history = read_jsonl_tail(BANDIT_HISTORY, 100)
    daemon = get_daemon_health()

    bandit_enabled = params_data.get("banditEnabled", False)
    param_count = len(params_data.get("parameters", []))
    total_decisions = bandit_data.get("sampleCounter", 0)

    # Average reward from last 100 history entries
    rewards = [e.get("reward", 0) for e in history if "reward" in e]
    avg_reward = round(sum(rewards) / len(rewards), 4) if rewards else None

    return {
        "banditEnabled": bandit_enabled,
        "daemonHealth": daemon,
        "paramCount": param_count,
        "totalDecisions": total_decisions,
        "avgRewardLast100": avg_reward,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_weight_history():
    """Read all JSON files from data/weight-snapshots/, return sorted array."""
    if not WEIGHT_SNAPSHOTS.is_dir():
        return []
    entries = []
    for fp in sorted(WEIGHT_SNAPSHOTS.glob("*.json")):
        data = read_json(fp)
        if data and "weights" in data:
            entries.append({
                "date": data.get("date", fp.stem),
                "weights": data["weights"],
            })
    # Sort by date string (YYYY-MM-DD)
    entries.sort(key=lambda e: e["date"])
    return entries


def build_reward_trend(n: int = 200):
    """Read last N entries from bandit-history.jsonl, return reward array."""
    entries = read_jsonl_tail(BANDIT_HISTORY, n)
    result = []
    for e in entries:
        if "reward" in e:
            result.append({
                "timestamp": e.get("timestamp", e.get("ts", "")),
                "reward": e["reward"],
            })
    return result


def build_timeline_response():
    """Read rollback and A/B reports, merge and sort by timestamp descending."""
    events = []

    # Rollback reports
    if ROLLBACK_REPORTS_DIR.is_dir():
        for fp in ROLLBACK_REPORTS_DIR.iterdir():
            if fp.suffix == ".json":
                data = read_json(fp)
                if data:
                    events.append({
                        "type": "rollback",
                        "timestamp": data.get("timestamp", ""),
                        "data": data,
                    })

    # A/B test reports
    if AB_REPORTS_DIR.is_dir():
        for fp in AB_REPORTS_DIR.iterdir():
            if fp.suffix == ".json":
                data = read_json(fp)
                if data:
                    events.append({
                        "type": "ab_test",
                        "timestamp": data.get("timestamp", ""),
                        "data": data,
                    })

    # Sort descending by timestamp
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return events


# ---------------------------------------------------------------------------
# Request Handler
# ---------------------------------------------------------------------------

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class DashboardHandler(SimpleHTTPRequestHandler):
    """Routes /api/* to data handlers, everything else to static files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    # Suppress default logging noise
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_options(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._handle_options()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # API routes
        if path == "/api/health":
            return self._send_json(build_health_response())

        if path == "/api/params":
            data = read_json(LEARNABLE_PARAMS)
            if data is None:
                return self._send_json({"error": "learnable-params.json not found"}, 404)
            return self._send_json(data)

        if path == "/api/bandit-state":
            data = read_json(BANDIT_STATE)
            if data is None:
                return self._send_json({"error": "bandit-state.json not found"}, 404)
            return self._send_json(data)

        if path == "/api/history":
            n = 100
            if "last" in qs:
                try:
                    n = int(qs["last"][0])
                except (ValueError, IndexError):
                    pass
            entries = read_jsonl_tail(BANDIT_HISTORY, n)
            return self._send_json({"count": len(entries), "entries": entries})

        if path == "/api/clusters":
            data = read_json(LRF_CLUSTERS)
            if data is None:
                return self._send_json({"error": "lrf-clusters.json not found"}, 404)
            return self._send_json(data)

        if path == "/api/cluster-projection":
            return self._handle_cluster_projection()

        if path == "/api/weight-history":
            entries = build_weight_history()
            return self._send_json(entries)

        if path == "/api/reward-trend":
            n = 200
            if "last" in qs:
                try:
                    n = int(qs["last"][0])
                except (ValueError, IndexError):
                    pass
            entries = build_reward_trend(n)
            return self._send_json(entries)

        if path == "/api/convergence":
            return self._handle_convergence()

        if path == "/api/timeline":
            return self._send_json(build_timeline_response())

        # Static files — default to index.html
        if path == "/":
            self.path = "/index.html"

        return super().do_GET()

    def _handle_convergence(self):
        """Serve multiplier convergence data from stability-monitor."""
        try:
            import importlib.util
            sm_path = DASHBOARD_DIR.parent / "stability-monitor.py"
            spec = importlib.util.spec_from_file_location("stability_monitor", str(sm_path))
            sm_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(sm_mod)
            return self._send_json(sm_mod.api_convergence())
        except Exception as exc:
            return self._send_json({"error": str(exc)}, 500)

    def _handle_cluster_projection(self):
        """Project cluster centroids to 2D via PCA, with mtime-based caching."""
        global _pca_cache

        data = read_json(LRF_CLUSTERS)
        if data is None:
            return self._send_json({"error": "lrf-clusters.json not found"}, 404)

        centroids = data.get("centroids", [])
        if not centroids:
            return self._send_json({"clusters": [], "silhouette": data.get("bestSilhouette")})

        # Check cache by mtime
        try:
            mtime = LRF_CLUSTERS.stat().st_mtime
        except OSError:
            mtime = 0.0

        if _pca_cache[0] == mtime and _pca_cache[1] is not None:
            return self._send_json(_pca_cache[1])

        # Import PCA from sibling module
        import importlib.util
        pca_path = DASHBOARD_DIR / "pca.py"
        spec = importlib.util.spec_from_file_location("pca", str(pca_path))
        pca_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pca_mod)

        points_2d = pca_mod.project_to_2d(centroids)

        cluster_sizes = data.get("cluster_sizes", [])
        cluster_avg_rewards = data.get("cluster_avg_rewards", [])
        clusters_meta = data.get("clusters", [])

        result_clusters = []
        for i, (px, py) in enumerate(points_2d):
            dc = 0
            er = 0.0
            if i < len(clusters_meta):
                dc = clusters_meta[i].get("decisionCount", 0)
                er = clusters_meta[i].get("clusterExplorationRate", 0.0)
            size = cluster_sizes[i] if i < len(cluster_sizes) else 0
            result_clusters.append({
                "x": px,
                "y": py,
                "clusterId": i,
                "size": size,
                "decisionCount": dc if dc else size,
                "avgReward": cluster_avg_rewards[i] if i < len(cluster_avg_rewards) else 0.0,
                "explorationRate": er,
            })

        response = {
            "clusters": result_clusters,
            "silhouette": data.get("bestSilhouette"),
            "k": data.get("k"),
            "updated": data.get("updated"),
        }

        _pca_cache = (mtime, response)
        return self._send_json(response)

    def end_headers(self):
        # Add CORS to all static-file responses too
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="meta-vengine dashboard server")
    parser.add_argument("--port", type=int, default=8420, help="Port to listen on (default: 8420)")
    args = parser.parse_args()

    server = HTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard: http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
