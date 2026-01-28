#!/bin/bash
# Project Progress Tracking Skill
# Displays comprehensive progress on any project across multiple data sources
# Usage: /project-progress [project-name] [action]

set -euo pipefail

# Configuration
PROJECTS_DIR="${HOME}/.claude/projects"
CACHE_DIR="${HOME}/.claude/tmp"

# Colors
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# ════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  $1${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_section() {
    echo -e "${YELLOW}${BOLD}→ $1${NC}"
}

progress_bar() {
    local percent=$1
    local width=${2:-20}

    [[ $percent -gt 100 ]] && percent=100
    [[ $percent -lt 0 ]] && percent=0

    local filled=$(( (percent * width) / 100 ))
    local empty=$((width - filled))

    if (( filled > 0 )); then
        printf '█%.0s' $(seq 1 $filled)
    fi
    if (( empty > 0 )); then
        printf '░%.0s' $(seq 1 $empty)
    fi
}

ensure_project_dir() {
    local project="$1"
    local project_dir="${PROJECTS_DIR}/${project}"

    if [[ ! -d "$project_dir" ]]; then
        mkdir -p "$project_dir"

        # Create default progress.json structure
        cat > "${project_dir}/progress.json" << 'EOF'
{
  "project_name": "PROJECT_NAME",
  "project_slug": "PROJECT_SLUG",
  "created_at": "CREATED_AT",
  "last_updated": "LAST_UPDATED",
  "status": "active",
  "completion": {
    "percent": 0,
    "tasks_completed": 0,
    "tasks_outstanding": 0,
    "milestones": []
  },
  "plan": {
    "title": "",
    "summary": "",
    "steps": [],
    "blockers": []
  },
  "sessions": []
}
EOF
        sed -i '' \
            -e "s|PROJECT_NAME|$project|g" \
            -e "s|PROJECT_SLUG|$(echo $project | tr '[:upper:]' '[:lower:]')|g" \
            -e "s|CREATED_AT|$(date -u +%Y-%m-%dT%H:%M:%SZ)|g" \
            -e "s|LAST_UPDATED|$(date -u +%Y-%m-%dT%H:%M:%SZ)|g" \
            "${project_dir}/progress.json"
    fi

    echo "$project_dir"
}

# ════════════════════════════════════════════════════════════════════════════
# DATA SOURCES: GIT
# ════════════════════════════════════════════════════════════════════════════

detect_project_root() {
    local project_name="$1"

    case "$project_name" in
        *[Oo][Ss]-[Aa]pp*)
            echo "${HOME}/OS-App"
            ;;
        *[Cc]areer*)
            echo "${HOME}/CareerCoachAntigravity"
            ;;
        *research*)
            echo "${HOME}/researchgravity"
            ;;
        *)
            echo "${HOME}/${project_name}"
            ;;
    esac
}

git_commit_count() {
    local project_root="$1"
    [[ ! -d "${project_root}/.git" ]] && echo "0" && return

    cd "$project_root" 2>/dev/null && git rev-list --count HEAD 2>/dev/null || echo "0"
}

git_changed_files() {
    local project_root="$1"
    local since="${2:-1 week ago}"

    [[ ! -d "${project_root}/.git" ]] && return

    cd "$project_root" 2>/dev/null && \
        git diff --name-only --since="$since" 2>/dev/null | wc -l || echo "0"
}

git_recent_activity() {
    local project_root="$1"
    local limit=${2:-5}

    [[ ! -d "${project_root}/.git" ]] && return

    cd "$project_root" 2>/dev/null && \
        git log --oneline -n "$limit" 2>/dev/null || true
}

# ════════════════════════════════════════════════════════════════════════════
# DATA SOURCES: JSON PROGRESS FILE
# ════════════════════════════════════════════════════════════════════════════

read_progress_file() {
    local project="$1"
    local project_dir=$(ensure_project_dir "$project")

    cat "${project_dir}/progress.json" 2>/dev/null || echo "{}"
}

update_progress_file() {
    local project="$1"
    local key="$2"
    local value="$3"

    local project_dir=$(ensure_project_dir "$project")
    local progress_file="${project_dir}/progress.json"

    # Update JSON with new value
    jq --arg key "$key" --arg val "$value" \
        '.[$key] = $val | .last_updated = now | strftime("%Y-%m-%dT%H:%M:%SZ")' \
        "$progress_file" > "${progress_file}.tmp" && \
        mv "${progress_file}.tmp" "$progress_file"
}

# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD: DISPLAY PROJECT PROGRESS
# ════════════════════════════════════════════════════════════════════════════

show_progress_dashboard() {
    local project="$1"

    print_header "PROJECT PROGRESS: $project"

    # Read data
    local progress_json=$(read_progress_file "$project")
    local project_root=$(detect_project_root "$project")

    # Extract from JSON
    local completion_pct=$(echo "$progress_json" | jq -r '.completion.percent // 0')
    local tasks_done=$(echo "$progress_json" | jq -r '.completion.tasks_completed // 0')
    local tasks_outstanding=$(echo "$progress_json" | jq -r '.completion.tasks_outstanding // 0')
    local total_tasks=$((tasks_done + tasks_outstanding))
    local plan_title=$(echo "$progress_json" | jq -r '.plan.title // "No plan set"')
    local plan_summary=$(echo "$progress_json" | jq -r '.plan.summary // ""')
    local blockers=$(echo "$progress_json" | jq -r '.plan.blockers[]? // empty' | wc -l)

    # ─── COMPLETION OVERVIEW ───
    print_section "Completion Overview"
    local bar=$(progress_bar "$completion_pct")
    echo "  Progress: $bar $completion_pct%"
    echo "  Tasks: ${GREEN}${tasks_done}${NC} completed / ${YELLOW}${tasks_outstanding}${NC} outstanding"
    [[ $total_tasks -gt 0 ]] && echo "  Rate: $((tasks_done * 100 / total_tasks))% of planned tasks complete"
    echo ""

    # ─── PLAN INFORMATION ───
    if [[ "$plan_title" != "No plan set" ]]; then
        print_section "Current Plan"
        echo "  Title: $plan_title"
        [[ -n "$plan_summary" ]] && echo "  Summary: $plan_summary"

        # Show plan steps
        local steps_count=$(echo "$progress_json" | jq '.plan.steps[]? // empty' | wc -l)
        if [[ $steps_count -gt 0 ]]; then
            echo "  Steps:"
            echo "$progress_json" | jq -r '.plan.steps[]? // empty' | nl -w1 -s') ' | sed 's/^/    /'
        fi
        echo ""
    fi

    # ─── OUTSTANDING ITEMS ───
    if [[ $tasks_outstanding -gt 0 ]]; then
        print_section "Outstanding Tasks"
        echo "  ${YELLOW}${tasks_outstanding} items remaining:${NC}"

        # Try to read from any outstanding-tasks file
        if [[ -f "${PROJECTS_DIR}/${project}/outstanding-tasks.txt" ]]; then
            sed 's/^/    - /' "${PROJECTS_DIR}/${project}/outstanding-tasks.txt"
        else
            echo "    (Use /project-progress update to track outstanding items)"
        fi
        echo ""
    fi

    # ─── BLOCKERS ───
    if [[ $blockers -gt 0 ]]; then
        print_section "Blockers"
        echo "$progress_json" | jq -r '.plan.blockers[]? // empty' | sed 's/^/  - /'
        echo ""
    fi

    # ─── GIT ACTIVITY ───
    if [[ -d "${project_root}/.git" ]]; then
        print_section "Recent Git Activity"
        local commits=$(git_commit_count "$project_root")
        local changes=$(git_changed_files "$project_root" "1 week ago")
        echo "  Total commits: $commits"
        echo "  Files changed (last week): $changes"
        echo ""

        if [[ $commits -gt 0 ]]; then
            echo "  Recent commits:"
            git_recent_activity "$project_root" 3 | sed 's/^/    /'
            echo ""
        fi
    fi

    # ─── MILESTONES ───
    local milestone_count=$(echo "$progress_json" | jq '.completion.milestones[]? // empty' | wc -l)
    if [[ $milestone_count -gt 0 ]]; then
        print_section "Milestones"
        echo "$progress_json" | jq -r '.completion.milestones[]? // empty' | sed 's/^/  ✓ /'
        echo ""
    fi
}

# ════════════════════════════════════════════════════════════════════════════
# UPDATE: INTERACTIVE PROGRESS UPDATE
# ════════════════════════════════════════════════════════════════════════════

interactive_update() {
    local project="$1"

    print_header "UPDATE PROJECT: $project"

    local project_dir=$(ensure_project_dir "$project")
    local progress_file="${project_dir}/progress.json"

    # Read current state
    local current_pct=$(jq -r '.completion.percent' "$progress_file")
    local current_done=$(jq -r '.completion.tasks_completed' "$progress_file")
    local current_outstanding=$(jq -r '.completion.tasks_outstanding' "$progress_file")

    echo "Current state:"
    echo "  Completion: ${current_pct}%"
    echo "  Done: ${current_done}, Outstanding: ${current_outstanding}"
    echo ""

    # Get updates
    read -p "New completion % [${current_pct}]: " new_pct
    new_pct="${new_pct:-$current_pct}"

    read -p "Tasks completed [${current_done}]: " new_done
    new_done="${new_done:-$current_done}"

    read -p "Outstanding tasks [${current_outstanding}]: " new_outstanding
    new_outstanding="${new_outstanding:-$current_outstanding}"

    read -p "Summary of work completed: " work_summary

    read -p "Any blockers? (leave blank if none): " blockers

    # Update progress.json
    jq \
        --arg percent "$new_pct" \
        --arg done "$new_done" \
        --arg outstanding "$new_outstanding" \
        --arg summary "$work_summary" \
        '.completion.percent = ($percent | tonumber) |
         .completion.tasks_completed = ($done | tonumber) |
         .completion.tasks_outstanding = ($outstanding | tonumber) |
         .last_updated = now | strftime("%Y-%m-%dT%H:%M:%SZ") |
         if $summary != "" then
           .sessions += [{"timestamp": now | strftime("%Y-%m-%dT%H:%M:%SZ"), "work_completed": $summary}]
         else . end' \
        "$progress_file" > "${progress_file}.tmp" && \
        mv "${progress_file}.tmp" "$progress_file"

    if [[ -n "$blockers" ]]; then
        jq --arg blocker "$blockers" \
            '.plan.blockers += [$blocker]' \
            "$progress_file" > "${progress_file}.tmp" && \
            mv "${progress_file}.tmp" "$progress_file"
    fi

    echo ""
    echo -e "${GREEN}✓ Progress updated${NC}"
    echo ""

    # Show new state
    show_progress_dashboard "$project"
}

# ════════════════════════════════════════════════════════════════════════════
# LIST ALL PROJECTS
# ════════════════════════════════════════════════════════════════════════════

list_projects() {
    print_header "ALL PROJECTS"

    if [[ ! -d "$PROJECTS_DIR" ]]; then
        echo "No projects tracked yet. Use '/project-progress [project-name] setup' to start tracking."
        return
    fi

    for project_dir in "${PROJECTS_DIR}"/*; do
        [[ ! -d "$project_dir" ]] && continue

        local project=$(basename "$project_dir")
        local progress_file="${project_dir}/progress.json"

        [[ ! -f "$progress_file" ]] && continue

        local pct=$(jq -r '.completion.percent // 0' "$progress_file")
        local status=$(jq -r '.status // "active"' "$progress_file")
        local bar=$(progress_bar "$pct" 15)

        echo "  ${BOLD}${project}${NC}"
        echo "    Progress: $bar $pct%"
        echo "    Status: $status"
        echo ""
    done
}

# ════════════════════════════════════════════════════════════════════════════
# MAIN DISPATCHER
# ════════════════════════════════════════════════════════════════════════════

main() {
    local project="${1:-}"
    local action="${2:-status}"

    if [[ -z "$project" ]]; then
        list_projects
        return
    fi

    case "$action" in
        status|show)
            show_progress_dashboard "$project"
            ;;
        update)
            interactive_update "$project"
            ;;
        setup)
            ensure_project_dir "$project"
            echo -e "${GREEN}✓ Project tracking initialized for: ${project}${NC}"
            ;;
        *)
            echo "Usage: /project-progress [project-name] [action]"
            echo ""
            echo "Actions:"
            echo "  status  - Show project progress dashboard (default)"
            echo "  update  - Update progress interactively"
            echo "  setup   - Initialize tracking for new project"
            echo "  (empty) - List all projects"
            ;;
    esac
}

main "$@"
