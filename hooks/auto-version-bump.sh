#!/bin/bash
# Auto Version Bump Hook
# Automatically bumps CLAUDE.md version when it's modified

CLAUDE_MD="$HOME/.claude/CLAUDE.md"
VERSION_MANAGER="$HOME/.claude/scripts/version-manager.sh"
CHECKSUM_FILE="$HOME/.claude/versions/.claude-md-checksum"

# Only proceed if the file being modified is CLAUDE.md
FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Check if this is a CLAUDE.md modification
if [[ "$FILE_PATH" == *"CLAUDE.md"* ]] || [[ "$FILE_PATH" == "$CLAUDE_MD" ]]; then
    # Get current checksum
    if [ -f "$CLAUDE_MD" ]; then
        CURRENT_CHECKSUM=$(shasum -a 256 "$CLAUDE_MD" 2>/dev/null | cut -d' ' -f1)

        # Get stored checksum
        STORED_CHECKSUM=""
        if [ -f "$CHECKSUM_FILE" ]; then
            STORED_CHECKSUM=$(cat "$CHECKSUM_FILE" 2>/dev/null)
        fi

        # Compare checksums
        if [ "$CURRENT_CHECKSUM" != "$STORED_CHECKSUM" ]; then
            # Content changed - bump version
            if [ -f "$VERSION_MANAGER" ]; then
                # Auto-bump patch version
                "$VERSION_MANAGER" bump patch >/dev/null 2>&1

                # Update stored checksum
                echo "$CURRENT_CHECKSUM" > "$CHECKSUM_FILE"

                # Log the auto-bump
                echo "{\"ts\":$(date +%s),\"event\":\"auto_version_bump\",\"file\":\"$FILE_PATH\"}" >> "$HOME/.claude/data/version-events.jsonl"

                echo "Auto-bumped CLAUDE.md version (content changed)"
            fi
        fi
    fi
fi
