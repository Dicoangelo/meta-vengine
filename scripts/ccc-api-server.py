#!/usr/bin/env python3
"""
CCC API Server - Full REST API for Claude Command Center

Endpoints:
- GET /api/stats         - Session stats and usage data
- GET /api/cost          - Cost data and savings
- GET /api/routing       - Routing metrics and DQ scores
- GET /api/sessions      - Session outcomes
- GET /api/tools         - Tool usage statistics
- GET /api/git           - Git activity
- GET /api/health        - System health check
- GET /api/fate          - Fate predictions

Run: python3 ccc-api-server.py [--port 8766]
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
PORT = 8766

class CCCAPIHandler(BaseHTTPRequestHandler):
    """API handler for CCC data."""

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def load_json(self, path):
        """Load JSON file."""
        try:
            with open(path) as f:
                return json.load(f)
        except:
            return {}

    def load_jsonl(self, path, limit=100):
        """Load JSONL file (last N entries)."""
        entries = []
        try:
            with open(path) as f:
                for line in f:
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except:
                            pass
            return entries[-limit:] if limit else entries
        except:
            return []

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        routes = {
            '/api/stats': self.get_stats,
            '/api/cost': self.get_cost,
            '/api/routing': self.get_routing,
            '/api/sessions': self.get_sessions,
            '/api/tools': self.get_tools,
            '/api/git': self.get_git,
            '/api/health': self.get_health,
            '/api/fate': self.get_fate,
            '/api/cognitive': self.get_cognitive,
            '/': self.get_index,
        }

        handler = routes.get(path)
        if handler:
            handler(params)
        else:
            self.send_json({"error": "Not found", "endpoints": list(routes.keys())}, 404)

    def get_index(self, params):
        """API index."""
        self.send_json({
            "name": "CCC API Server",
            "version": "1.0.0",
            "endpoints": [
                {"path": "/api/stats", "description": "Session stats and usage"},
                {"path": "/api/cost", "description": "Cost data and savings"},
                {"path": "/api/routing", "description": "Routing metrics"},
                {"path": "/api/sessions", "description": "Session outcomes"},
                {"path": "/api/tools", "description": "Tool usage stats"},
                {"path": "/api/git", "description": "Git activity"},
                {"path": "/api/health", "description": "System health"},
                {"path": "/api/fate", "description": "Fate predictions"},
                {"path": "/api/cognitive", "description": "Cognitive OS state"},
            ],
            "timestamp": datetime.now().isoformat()
        })

    def get_stats(self, params):
        """Session statistics."""
        data = self.load_json(CLAUDE_DIR / "stats-cache.json")
        self.send_json(data)

    def get_cost(self, params):
        """Cost data."""
        data = self.load_json(CLAUDE_DIR / "kernel/cost-data.json")
        self.send_json(data)

    def get_routing(self, params):
        """Routing metrics."""
        limit = int(params.get('limit', [100])[0])
        dq_scores = self.load_jsonl(CLAUDE_DIR / "kernel/dq-scores.jsonl", limit)
        routing = self.load_jsonl(CLAUDE_DIR / "data/routing-metrics.jsonl", limit)
        feedback = self.load_jsonl(CLAUDE_DIR / "data/routing-feedback.jsonl", limit)

        self.send_json({
            "dq_scores": dq_scores,
            "routing_metrics": routing,
            "feedback": feedback,
            "total_dq": len(dq_scores),
            "total_routing": len(routing),
            "total_feedback": len(feedback)
        })

    def get_sessions(self, params):
        """Session outcomes."""
        limit = int(params.get('limit', [50])[0])
        sessions = self.load_jsonl(CLAUDE_DIR / "data/session-outcomes.jsonl", limit)
        self.send_json({"sessions": sessions, "count": len(sessions)})

    def get_tools(self, params):
        """Tool usage."""
        limit = int(params.get('limit', [100])[0])
        usage = self.load_jsonl(CLAUDE_DIR / "data/tool-usage.jsonl", limit)
        success = self.load_jsonl(CLAUDE_DIR / "data/tool-success.jsonl", limit)

        self.send_json({
            "usage": usage,
            "success": success,
            "total_usage": len(usage),
            "total_success": len(success)
        })

    def get_git(self, params):
        """Git activity."""
        limit = int(params.get('limit', [50])[0])
        activity = self.load_jsonl(CLAUDE_DIR / "data/git-activity.jsonl", limit)
        self.send_json({"activity": activity, "count": len(activity)})

    def get_health(self, params):
        """System health."""
        import subprocess

        # Check daemons
        try:
            result = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
            daemons = [l for l in result.stdout.split('\n') if 'com.claude' in l]
        except:
            daemons = []

        # Check data freshness
        cost_file = CLAUDE_DIR / "kernel/cost-data.json"
        cost_age = (datetime.now().timestamp() - cost_file.stat().st_mtime) / 60 if cost_file.exists() else -1

        self.send_json({
            "status": "healthy" if cost_age < 5 else "stale",
            "daemons_count": len(daemons),
            "cost_data_age_minutes": round(cost_age, 1),
            "timestamp": datetime.now().isoformat()
        })

    def get_fate(self, params):
        """Fate predictions."""
        limit = int(params.get('limit', [50])[0])
        predictions = self.load_jsonl(CLAUDE_DIR / "kernel/cognitive-os/fate-predictions.jsonl", limit)

        correct = sum(1 for p in predictions if p.get("correct"))
        total = len(predictions)
        accuracy = correct / total * 100 if total > 0 else 0

        self.send_json({
            "predictions": predictions,
            "accuracy": round(accuracy, 1),
            "correct": correct,
            "total": total
        })

    def get_cognitive(self, params):
        """Cognitive OS state."""
        state = self.load_json(CLAUDE_DIR / "kernel/cognitive-os/current-state.json")
        flow = self.load_json(CLAUDE_DIR / "kernel/cognitive-os/flow-state.json")
        weekly = self.load_json(CLAUDE_DIR / "kernel/cognitive-os/weekly-energy.json")

        self.send_json({
            "current_state": state,
            "flow_state": flow,
            "weekly_energy": weekly
        })


def main():
    port = PORT
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    server = HTTPServer(('localhost', port), CCCAPIHandler)
    print(f"CCC API Server running on http://localhost:{port}")
    print(f"Endpoints: /api/stats, /api/cost, /api/routing, /api/sessions, /api/tools, /api/git, /api/health, /api/fate")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
