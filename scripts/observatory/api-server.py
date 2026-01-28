#!/usr/bin/env python3
"""
Simple API server for Autonomous Analysis Dashboard
Serves session-outcomes.jsonl data
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
from urllib.parse import urlparse


class DashboardAPIHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves both static files and API endpoints."""

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # API endpoint: /api/sessions
        if path == '/api/sessions':
            self.serve_sessions()
        # API endpoint: /api/baselines
        elif path == '/api/baselines':
            self.serve_baselines()
        # Static files (HTML, CSS, JS)
        else:
            # Serve from current directory
            super().do_GET()

    def serve_sessions(self):
        """Serve session-outcomes.jsonl as JSON array."""
        try:
            outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

            if not outcomes_file.exists():
                self.send_error(404, "session-outcomes.jsonl not found")
                return

            # Load all entries
            entries = []
            with open(outcomes_file) as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            self.wfile.write(json.dumps(entries).encode())

        except Exception as e:
            self.send_error(500, str(e))

    def serve_baselines(self):
        """Serve baselines.json."""
        try:
            baselines_file = Path.home() / ".claude/kernel/baselines.json"

            if not baselines_file.exists():
                self.send_error(404, "baselines.json not found")
                return

            with open(baselines_file) as f:
                baselines = json.load(f)

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            self.wfile.write(json.dumps(baselines).encode())

        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, format, *args):
        """Suppress log messages for cleaner output."""
        pass


def main():
    # Change to scripts directory where dashboard HTML is
    import os
    scripts_dir = Path.home() / ".claude/scripts"
    os.chdir(scripts_dir)

    port = 8888
    server = HTTPServer(('127.0.0.1', port), DashboardAPIHandler)

    print(f"🚀 Dashboard API Server running on http://127.0.0.1:{port}")
    print(f"📊 Open dashboard: http://127.0.0.1:{port}/autonomous-analysis-dashboard.html")
    print("\nPress Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped")


if __name__ == "__main__":
    main()
