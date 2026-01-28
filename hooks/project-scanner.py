#!/usr/bin/env python3
"""
Project Scanner for Antigravity Ecosystem
Scans known project directories and indexes them in antigravity.db

Usage:
    python3 project-scanner.py           # Scan all known projects
    python3 project-scanner.py --list    # List indexed projects
    python3 project-scanner.py --add /path/to/project  # Add a new project
"""

import sqlite3
import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".agent-core" / "storage" / "antigravity.db"

# Known project directories
KNOWN_PROJECTS = {
    "os-app": {
        "path": Path.home() / "OS-App",
        "name": "OS-App",
        "type": "vite",
        "metadata": {
            "stack": ["React 19", "Vite", "Zustand", "TypeScript"],
            "focus": ["agentic-os", "biometric-ui", "multi-agent-orchestration"]
        }
    },
    "careercoach": {
        "path": Path.home() / "CareerCoachAntigravity",
        "name": "CareerCoachAntigravity",
        "type": "nextjs",
        "metadata": {
            "stack": ["Next.js 14", "React 18", "Zustand", "TypeScript"],
            "focus": ["career-intelligence", "ai-agents", "resume-builder"]
        }
    },
    "researchgravity": {
        "path": Path.home() / "researchgravity",
        "name": "ResearchGravity",
        "type": "python",
        "metadata": {
            "stack": ["Python 3.8+"],
            "focus": ["research-tracking", "auto-capture", "session-management"]
        }
    },
    "metaventions": {
        "path": Path.home() / "Metaventions-AI-Landing",
        "name": "Metaventions-AI-Landing",
        "type": "vite",
        "metadata": {
            "stack": ["React", "Vite", "Three.js"],
            "focus": ["landing-page", "3d-visualization"]
        }
    },
    "decosystem": {
        "path": Path.home() / "The-Decosystem",
        "name": "The-Decosystem",
        "type": "monorepo",
        "metadata": {
            "stack": ["Multi-project"],
            "focus": ["ecosystem-registry", "documentation"]
        }
    },
    "agent-core": {
        "path": Path.home() / ".agent-core",
        "name": "Agent Core",
        "type": "data",
        "metadata": {
            "stack": ["SQLite", "JSON"],
            "focus": ["unified-data", "research-index", "cognitive-wallet"]
        }
    },
    "claude-config": {
        "path": Path.home() / ".claude",
        "name": "Claude Config",
        "type": "config",
        "metadata": {
            "stack": ["JSON", "Python", "Bash"],
            "focus": ["hooks", "scripts", "kernel"]
        }
    }
}


def get_db():
    """Get database connection."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def get_git_remote(project_path: Path) -> str:
    """Get git remote URL if available."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return None


def get_last_activity(project_path: Path) -> str:
    """Get last git commit timestamp or file modification time."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "log", "-1", "--format=%ci"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except:
        pass

    # Fallback to directory mtime
    try:
        mtime = os.path.getmtime(project_path)
        return datetime.fromtimestamp(mtime).isoformat()
    except:
        return None


def scan_project(project_id: str, config: dict) -> dict:
    """Scan a single project and return its data."""
    path = config["path"]

    if not path.exists():
        return None

    return {
        "id": project_id,
        "name": config["name"],
        "path": str(path),
        "type": config["type"],
        "status": "active",
        "git_remote": get_git_remote(path),
        "last_activity": get_last_activity(path),
        "metadata": json.dumps(config.get("metadata", {}))
    }


def upsert_project(conn, project_data: dict):
    """Insert or update a project in the database."""
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO projects (id, name, path, type, status, git_remote, last_activity, metadata, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            path = excluded.path,
            type = excluded.type,
            status = excluded.status,
            git_remote = excluded.git_remote,
            last_activity = excluded.last_activity,
            metadata = excluded.metadata,
            updated_at = datetime('now')
    """, (
        project_data["id"],
        project_data["name"],
        project_data["path"],
        project_data["type"],
        project_data["status"],
        project_data["git_remote"],
        project_data["last_activity"],
        project_data["metadata"]
    ))


def scan_all():
    """Scan all known projects and update the database."""
    conn = get_db()

    scanned = 0
    for project_id, config in KNOWN_PROJECTS.items():
        data = scan_project(project_id, config)
        if data:
            upsert_project(conn, data)
            scanned += 1
            print(f"  [+] {project_id}: {config['path']}")
        else:
            print(f"  [-] {project_id}: not found")

    conn.commit()
    conn.close()

    print(f"\nScanned {scanned} projects → ~/.agent-core/storage/antigravity.db")


def list_projects():
    """List all indexed projects."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, type, status, last_activity
        FROM projects
        ORDER BY last_activity DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("No projects indexed yet. Run: python3 project-scanner.py")
        return

    print("\n╔════════════════════════════════════════════════════════════════╗")
    print("║                    INDEXED PROJECTS                            ║")
    print("╠════════════════════════════════════════════════════════════════╣")
    print("║ ID                │ Type    │ Status │ Last Activity          ║")
    print("╠═══════════════════╪═════════╪════════╪════════════════════════╣")

    for row in rows:
        pid, name, ptype, status, activity = row
        activity_short = activity[:19] if activity else "N/A"
        print(f"║ {pid:<17} │ {ptype:<7} │ {status:<6} │ {activity_short:<22} ║")

    print("╚════════════════════════════════════════════════════════════════╝")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            list_projects()
            return
        elif sys.argv[1] == "--add" and len(sys.argv) > 2:
            # Add custom project - future enhancement
            print("Custom project addition not yet implemented")
            return

    print("Scanning projects...")
    scan_all()


if __name__ == "__main__":
    main()
