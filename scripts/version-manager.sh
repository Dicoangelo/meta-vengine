#!/bin/bash
# Meta-Vengine Version Manager
# Semantic versioning for CLAUDE.md prompts and agent definitions

VERSION_DIR="$HOME/.claude/versions"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
VERSION_FILE="$VERSION_DIR/VERSION"
CHANGELOG="$VERSION_DIR/CHANGELOG.md"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

# Initialize versioning if needed
init_versioning() {
    if [[ ! -f "$VERSION_FILE" ]]; then
        echo "2.0.0" > "$VERSION_FILE"

        # Create initial CHANGELOG
        cat > "$CHANGELOG" << 'EOF'
# CLAUDE.md Version Changelog

## [2.0.0] - Initial Versioning
- Established semantic versioning for CLAUDE.md
- Added version tracking header
- Created version-manager.sh for management

EOF

        # Archive initial version
        if [[ -f "$CLAUDE_MD" ]]; then
            cp "$CLAUDE_MD" "$VERSION_DIR/prompts/CLAUDE.md.v2.0.0"
            add_version_header
        fi

        echo -e "${GREEN}Versioning initialized at v2.0.0${RESET}"
    fi
}

# Get current version
get_version() {
    if [[ -f "$VERSION_FILE" ]]; then
        cat "$VERSION_FILE"
    else
        echo "0.0.0"
    fi
}

# Add version header to CLAUDE.md
add_version_header() {
    local version=$(get_version)
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local checksum=$(shasum -a 256 "$CLAUDE_MD" 2>/dev/null | cut -d' ' -f1)

    # Check if header already exists
    if grep -q "^<!-- VERSION:" "$CLAUDE_MD" 2>/dev/null; then
        # Update existing header
        sed -i '' "s/<!-- VERSION: .* -->/<!-- VERSION: $version -->/" "$CLAUDE_MD"
        sed -i '' "s/<!-- LAST_MODIFIED: .* -->/<!-- LAST_MODIFIED: $timestamp -->/" "$CLAUDE_MD"
        sed -i '' "s/<!-- CHECKSUM: .* -->/<!-- CHECKSUM: sha256:${checksum:0:16}... -->/" "$CLAUDE_MD"
    else
        # Add new header at the top
        local temp_file=$(mktemp)
        cat > "$temp_file" << EOF
<!-- VERSION: $version -->
<!-- LAST_MODIFIED: $timestamp -->
<!-- CHECKSUM: sha256:${checksum:0:16}... -->

EOF
        cat "$CLAUDE_MD" >> "$temp_file"
        mv "$temp_file" "$CLAUDE_MD"
    fi
}

# Bump version
bump_version() {
    local bump_type="${1:-patch}"
    local current=$(get_version)

    # Parse current version
    IFS='.' read -r major minor patch <<< "$current"

    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            echo -e "${RED}Invalid bump type: $bump_type${RESET}"
            echo "Usage: prompt-bump [major|minor|patch]"
            return 1
            ;;
    esac

    local new_version="${major}.${minor}.${patch}"

    # Archive current version before bump
    if [[ -f "$CLAUDE_MD" ]]; then
        cp "$CLAUDE_MD" "$VERSION_DIR/prompts/CLAUDE.md.v$current"
    fi

    # Update version file
    echo "$new_version" > "$VERSION_FILE"

    # Update CLAUDE.md header
    add_version_header

    # Add changelog entry
    local timestamp=$(date +"%Y-%m-%d")
    local temp_changelog=$(mktemp)

    if [[ -f "$CHANGELOG" ]]; then
        head -n 2 "$CHANGELOG" > "$temp_changelog"
        echo "" >> "$temp_changelog"
        echo "## [$new_version] - $timestamp" >> "$temp_changelog"
        echo "- Bumped from $current" >> "$temp_changelog"
        echo "" >> "$temp_changelog"
        tail -n +3 "$CHANGELOG" >> "$temp_changelog"
        mv "$temp_changelog" "$CHANGELOG"
    fi

    echo -e "${GREEN}Version bumped: $current -> $new_version${RESET}"
    echo "Archived: $VERSION_DIR/prompts/CLAUDE.md.v$current"
}

# Rollback to a specific version
rollback_version() {
    local target="$1"

    if [[ -z "$target" ]]; then
        echo -e "${RED}Usage: prompt-rollback <version>${RESET}"
        echo "Available versions:"
        list_versions
        return 1
    fi

    local archive="$VERSION_DIR/prompts/CLAUDE.md.v$target"

    if [[ ! -f "$archive" ]]; then
        echo -e "${RED}Version $target not found${RESET}"
        echo "Available versions:"
        list_versions
        return 1
    fi

    local current=$(get_version)

    # Archive current before rollback
    cp "$CLAUDE_MD" "$VERSION_DIR/prompts/CLAUDE.md.v$current.pre-rollback"

    # Restore target version
    cp "$archive" "$CLAUDE_MD"
    echo "$target" > "$VERSION_FILE"

    echo -e "${GREEN}Rolled back: $current -> $target${RESET}"
    echo "Previous version saved as: CLAUDE.md.v$current.pre-rollback"
}

# Show diff between versions
diff_versions() {
    local v1="$1"
    local v2="${2:-$(get_version)}"

    if [[ -z "$v1" ]]; then
        echo -e "${RED}Usage: prompt-diff <version1> [version2]${RESET}"
        echo "If version2 is omitted, compares to current"
        list_versions
        return 1
    fi

    local file1="$VERSION_DIR/prompts/CLAUDE.md.v$v1"
    local file2

    if [[ "$v2" == "$(get_version)" ]] && [[ -f "$CLAUDE_MD" ]]; then
        file2="$CLAUDE_MD"
    else
        file2="$VERSION_DIR/prompts/CLAUDE.md.v$v2"
    fi

    if [[ ! -f "$file1" ]]; then
        echo -e "${RED}Version $v1 not found${RESET}"
        return 1
    fi

    if [[ ! -f "$file2" ]]; then
        echo -e "${RED}Version $v2 not found${RESET}"
        return 1
    fi

    echo -e "${CYAN}Diff: v$v1 -> v$v2${RESET}"
    echo "-------------------------------------------"
    diff --color=auto -u "$file1" "$file2" || true
}

# List all versions
list_versions() {
    echo -e "${CYAN}Available versions:${RESET}"
    ls -1 "$VERSION_DIR/prompts/" 2>/dev/null | grep "CLAUDE.md.v" | sed 's/CLAUDE.md.v/  /' | sort -V
    echo ""
    echo -e "Current: ${GREEN}$(get_version)${RESET}"
}

# Archive an agent definition
archive_agent() {
    local agent_name="$1"
    local version="${2:-1.0.0}"
    local agent_file="$HOME/.claude/scripts/observatory/agents/${agent_name}.py"

    if [[ ! -f "$agent_file" ]]; then
        echo -e "${RED}Agent not found: $agent_file${RESET}"
        return 1
    fi

    local archive_file="$VERSION_DIR/agents/${agent_name}.v${version}.py"
    cp "$agent_file" "$archive_file"

    echo -e "${GREEN}Archived: ${agent_name} v${version}${RESET}"
}

# Show version status
show_status() {
    echo -e "${CYAN}Meta-Vengine Version Status${RESET}"
    echo "========================================"
    echo -e "CLAUDE.md Version: ${GREEN}$(get_version)${RESET}"
    echo -e "Last Modified:     $(grep 'LAST_MODIFIED' "$CLAUDE_MD" 2>/dev/null | sed 's/.*: //' | sed 's/ -->//')"
    echo ""
    echo "Archived Versions:"
    ls -1 "$VERSION_DIR/prompts/" 2>/dev/null | wc -l | xargs echo "  Prompts:"
    ls -1 "$VERSION_DIR/agents/" 2>/dev/null | wc -l | xargs echo "  Agents: "
    echo ""
    echo "Recent Changes (last 5):"
    head -20 "$CHANGELOG" 2>/dev/null | tail -15
}

# Main command handler
case "${1:-}" in
    init)
        init_versioning
        ;;
    version|get)
        get_version
        ;;
    bump)
        init_versioning
        bump_version "${2:-patch}"
        ;;
    rollback)
        rollback_version "$2"
        ;;
    diff)
        diff_versions "$2" "$3"
        ;;
    list)
        list_versions
        ;;
    archive-agent)
        archive_agent "$2" "$3"
        ;;
    status)
        show_status
        ;;
    help|*)
        echo "Meta-Vengine Version Manager"
        echo ""
        echo "Usage: version-manager.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  init              Initialize versioning system"
        echo "  version           Show current version"
        echo "  bump [type]       Bump version (major|minor|patch)"
        echo "  rollback <ver>    Rollback to specific version"
        echo "  diff <v1> [v2]    Show diff between versions"
        echo "  list              List all archived versions"
        echo "  archive-agent     Archive an agent definition"
        echo "  status            Show version status"
        echo ""
        echo "Aliases (add to init.sh):"
        echo "  prompt-version    -> version-manager.sh version"
        echo "  prompt-bump       -> version-manager.sh bump"
        echo "  prompt-rollback   -> version-manager.sh rollback"
        echo "  prompt-diff       -> version-manager.sh diff"
        ;;
esac
