#!/bin/bash
# Install git hooks in all tracked projects

HOOK_SOURCE="$HOME/.claude/hooks/git-post-commit.sh"
CONFIG_FILE="$HOME/.claude/config/system.json"

if [ ! -f "$HOOK_SOURCE" ]; then
    echo "❌ Hook source not found: $HOOK_SOURCE"
    exit 1
fi

# Read projects from config
PROJECTS=$(python3 -c "
import json
from pathlib import Path
home = Path.home()
with open(home / '.claude/config/system.json') as f:
    config = json.load(f)
for p in config.get('projects', []):
    path = str(p['path']).replace('~', str(home))
    print(path)
")

installed=0
skipped=0

for project in $PROJECTS; do
    if [ -d "$project/.git" ]; then
        hook_path="$project/.git/hooks/post-commit"
        if [ -L "$hook_path" ] && [ "$(readlink "$hook_path")" = "$HOOK_SOURCE" ]; then
            echo "⏭️ Already installed: $(basename "$project")"
            ((skipped++))
        else
            ln -sf "$HOOK_SOURCE" "$hook_path"
            echo "✅ Installed: $(basename "$project")"
            ((installed++))
        fi
    fi
done

echo ""
echo "Done: $installed installed, $skipped already had hooks"
