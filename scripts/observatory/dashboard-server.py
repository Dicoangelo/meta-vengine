#!/usr/bin/env python3
"""
Dashboard Server

Serves the autonomous analysis dashboard with live data.
"""

import json
import http.server
import socketserver
from pathlib import Path
from urllib.parse import urlparse

PORT = 8765
DATA_DIR = Path.home() / ".claude/data"
KERNEL_DIR = Path.home() / ".claude/kernel"
SCRIPTS_DIR = Path.home() / ".claude/scripts"


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for dashboard requests."""

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Serve HTML dashboard
        if path == '/' or path == '/index.html':
            self.serve_dashboard()

        # Serve session outcomes data
        elif path == '/api/sessions':
            self.serve_sessions_data()

        # Serve baselines data
        elif path == '/api/baselines':
            self.serve_baselines_data()

        else:
            self.send_error(404, "Not found")

    def serve_dashboard(self):
        """Serve the dashboard HTML."""
        dashboard_file = SCRIPTS_DIR / "autonomous-analysis-dashboard.html"

        try:
            with open(dashboard_file, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            self.send_error(500, f"Error serving dashboard: {e}")

    def serve_sessions_data(self):
        """Serve session outcomes as JSON."""
        sessions_file = DATA_DIR / "session-outcomes.jsonl"

        try:
            sessions = []
            if sessions_file.exists():
                with open(sessions_file) as f:
                    for line in f:
                        if line.strip():
                            sessions.append(json.loads(line))

            # Convert to JSON
            data = json.dumps(sessions, indent=2)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(data))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())

        except Exception as e:
            self.send_error(500, f"Error serving sessions: {e}")

    def serve_baselines_data(self):
        """Serve baselines data as JSON."""
        baselines_file = KERNEL_DIR / "baselines.json"

        try:
            if baselines_file.exists():
                with open(baselines_file) as f:
                    baselines = json.load(f)
            else:
                baselines = {"feedback_lineage": []}

            data = json.dumps(baselines, indent=2)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(data))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data.encode())

        except Exception as e:
            self.send_error(500, f"Error serving baselines: {e}")


def main():
    """Start the dashboard server."""

    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print(f"🚀 Autonomous Analysis Dashboard Server")
        print(f"=" * 70)
        print(f"\n📊 Dashboard URL: http://localhost:{PORT}")
        print(f"\nPress Ctrl+C to stop the server\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✅ Server stopped")


if __name__ == "__main__":
    main()
