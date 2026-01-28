# Project Progress Tracking Skill

**Purpose**: Track and visualize progress across all your projects, perfect for resuming work in new CLI sessions.

## Quick Start

### List all projects
```bash
/project-progress
```

Shows all tracked projects with completion %, status, and recent activity.

### Setup a new project
```bash
/project-progress [project-name] setup
```

Creates tracking infrastructure for a new project.

### View project dashboard
```bash
/project-progress [project-name]
# or
/project-progress [project-name] status
```

Shows comprehensive progress dashboard including:
- Overall completion % with visual progress bar
- Tasks completed / outstanding count
- Current plan title and summary
- Outstanding tasks list
- Recent git activity and commits
- Blockers (if any)

### Update project progress
```bash
/project-progress [project-name] update
```

Interactive prompt to:
- Update completion percentage
- Update task counts
- Record what work was completed
- Add blockers

## Data Sources

The skill automatically pulls from:

1. **JSON Progress Files** (`~/.claude/projects/[project]/progress.json`)
   - Completion %, task counts
   - Plan information
   - Blockers and milestones
   - Session history

2. **Git History**
   - Total commits
   - Files changed (last week)
   - Recent 5 commits
   - Detects activity automatically

3. **Manual Updates**
   - Interactive progress updates
   - Work summary logging
   - Blocker tracking

## Use Case: Resume a Session

**Scenario**: You start a new CLI session and want to continue work on OS-App

```bash
# 1. Check all projects at a glance
/project-progress

# Output shows:
#   OS-App
#     Progress: ███████░░░░░░░░░░░░░ 65%
#     Status: active

# 2. View detailed dashboard
/project-progress OS-App

# Shows:
#   - 65% complete, 13 tasks done, 7 outstanding
#   - Current plan: "Agentic kernel integration"
#   - Recent commits from last session
#   - Any blockers preventing progress

# 3. Ask Claude to continue
# "I see OS-App is at 65% with 7 outstanding tasks.
#  Here's what was blocking: [blocker from dashboard]
#  What should I work on next?"
```

## Data Structure

Each project gets a directory: `~/.claude/projects/[project]/`

### progress.json
```json
{
  "project_name": "OS-App",
  "project_slug": "os-app",
  "created_at": "2026-01-25T...",
  "last_updated": "2026-01-25T...",
  "status": "active",
  "completion": {
    "percent": 65,
    "tasks_completed": 13,
    "tasks_outstanding": 7,
    "milestones": ["Phase 1: Setup ✓", "Phase 2: Core (in progress)"]
  },
  "plan": {
    "title": "Agentic kernel integration",
    "summary": "Implementing multi-agent orchestration...",
    "steps": [...],
    "blockers": ["Dependency waiting on X", "Need clarification on Y"]
  },
  "sessions": [
    {
      "timestamp": "2026-01-25T...",
      "work_completed": "Implemented voting consensus..."
    }
  ]
}
```

## Supported Projects

Automatically detects common projects:
- OS-App (`~/OS-App`)
- CareerCoach (`~/CareerCoachAntigravity`)
- ResearchGravity (`~/researchgravity`)

For other projects, use the exact directory name or alias.

## Integration with Command Center

Add to your command center to see all projects at session start:

```bash
echo "Projects overview:"
/project-progress
```

## Examples

### Track a new project
```bash
$ /project-progress "MetaventionsPlatform" setup
✓ Project tracking initialized for: MetaventionsPlatform
```

### Update progress after a session
```bash
$ /project-progress OS-App update

Current state:
  Completion: 65%
  Done: 13, Outstanding: 7

New completion % [65]: 72
Tasks completed [13]: 16
Outstanding tasks [7]: 4
Summary of work completed: Implemented consensus voting, fixed edge cases
Any blockers? (leave blank if none): Waiting on Gemini API quota increase

✓ Progress updated
```

### View specific project
```bash
$ /project-progress CareerCoach

PROJECT PROGRESS: CareerCoach
──────────────────────────────
→ Completion Overview
  Progress: ████░░░░░░░░░░░ 32%
  Tasks: 4 completed / 8 outstanding
  Rate: 33% of planned tasks complete

→ Current Plan
  Title: Career governance system
  Summary: Building AI-powered career path recommendations

→ Recent Git Activity
  Total commits: 156
  Files changed (last week): 8

→ Outstanding Tasks
  8 items remaining:
    - Implement role-based access control
    - Add performance tracking dashboard
    - (Use /project-progress update to track more details)
```

## Tips

1. **Before starting a session**: Run `/project-progress` to see what's in progress
2. **After finishing work**: Run `/project-progress [project] update` to log progress
3. **When blocked**: Log blockers in the update prompt so you remember next session
4. **Plan reference**: The skill shows your current plan title/summary - use this to contextualize work

## Future Enhancements

Potential additions:
- Auto-detect progress from git commit messages (look for `#65%` or `[task: 4/8]`)
- Integration with task tracking (if using task lists)
- Milestone notifications when reaching thresholds
- Weekly progress reports
- Cross-project dependency tracking
- Burndown charts

---

**Files**:
- Skill: `~/.claude/skills/project-progress.sh`
- Data: `~/.claude/projects/*/progress.json`
- Config: `~/.claude/projects/*/` (project directories)
