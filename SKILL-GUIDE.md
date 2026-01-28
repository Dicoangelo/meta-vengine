# Claude Code Skill Guide

This guide explains the new skills created for tracking and visualizing project progress across your ecosystem.

---

## Skill #1: Statusline Command Generator (statusline-create.sh)

**Purpose**: Create metric-specific statusline displays for any data source
**Location**: `~/.claude/scripts/statusline-create.sh`

### Use Cases
- Real-time metric monitoring (context window, cache hit rate, token budget)
- Custom dashboards for CI/CD metrics
- Performance monitoring (memory, CPU, latency)
- Any JSON metric you want to visualize

### How It Works
1. Interactive setup wizard asks about your metric
2. Generates a custom shell script for that metric
3. Supports multiple data sources (stdin, file, command, hybrid)
4. Includes built-in caching for performance
5. Renders progress bars, gauges, or numeric displays

### Example: Context Window Statusline
We already created `~/.claude/statusline-command.sh`:
```bash
Haiku | ██████░░░░░░░░░░░░░░ 32% (27.8k/200k) | ~/OS-App | Session: abc12345
```

This displays in your Claude Code statusLine automatically (configured in settings.json).

---

## Skill #2: Project Progress Tracker (/project-progress)

**Purpose**: Track and visualize progress across all your projects
**Location**: `~/.claude/skills/project-progress.sh`

### The Problem It Solves

You're working on a complex project (e.g., OS-App). You get to 65% completion with some blockers. Then you:
- Close the terminal
- Work on other things
- Come back a week later with a new CLI session

**Without the skill**: You have no idea where you left off.
**With the skill**: You run `/project-progress OS-App` and see:
- 65% complete, 13 tasks done, 7 outstanding
- Current plan: "Agentic kernel integration"
- Blockers preventing progress
- Recent git activity from last session

### Quick Reference

```bash
# List all projects
/project-progress

# Setup new project
/project-progress MyProject setup

# View dashboard
/project-progress OS-App

# Update progress interactively
/project-progress OS-App update
```

### Typical Workflow

#### Starting a New Session
```bash
# 1. See all projects at a glance
$ /project-progress

OS-App
  Progress: █████████░░░░░░ 65%
  Status: active

# 2. View specific project details
$ /project-progress OS-App

PROJECT PROGRESS: OS-App
─────────────────────────
→ Completion Overview
  Progress: █████████░░░░░░ 65%
  Tasks: 13 completed / 7 outstanding

→ Current Plan
  Title: Agentic kernel integration
  Summary: Implementing multi-agent orchestration...

→ Outstanding Tasks
  7 items remaining:
    (Use /project-progress update to track)

→ Recent Git Activity
  Total commits: 444
  Files changed: 0 (no activity this week)
  Recent commits:
    062e584 fix(GeminiLive): Add echo prevention
    e43d39e refactor(Voice): Switch to Gemini Live
    f53923c refactor(UnifiedRegistry): Consolidate Tool Registries

→ Blockers
  (none)

# 3. Ask Claude to continue
"I see OS-App is at 65% with 7 outstanding tasks.
 Recent work was on GeminiLive integration.
 What should I focus on next?"
```

#### After Completing Work
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

### Data Structure

Each project gets tracked in: `~/.claude/projects/[project]/progress.json`

```json
{
  "project_name": "OS-App",
  "completion": {
    "percent": 65,
    "tasks_completed": 13,
    "tasks_outstanding": 7
  },
  "plan": {
    "title": "Agentic kernel integration",
    "summary": "...",
    "steps": [...],
    "blockers": ["Waiting on Gemini API quota"]
  },
  "sessions": [
    {
      "timestamp": "2026-01-25T...",
      "work_completed": "Implemented consensus voting..."
    }
  ]
}
```

### Auto-Detected Features

The skill automatically:
- Counts total git commits per project
- Tracks files changed in the last week
- Lists recent 5 commits
- Detects if a .git directory exists
- Recognizes your common projects:
  - OS-App → ~/OS-App
  - CareerCoach → ~/CareerCoachAntigravity
  - researchgravity → ~/researchgravity

---

## Integration: How They Work Together

### Scenario: New Session on OS-App

```
┌─────────────────────────────────────────────────────────┐
│ You start a new Claude Code CLI session                 │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│ STATUSLINE (continuous display at bottom)               │
│ Haiku | ██████░░░░░░░░░░░░░░ 32% (27.8k/200k) | OS-App │
│                                                         │
│ This shows you're in OS-App, context window is 32%      │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│ Run /project-progress OS-App                            │
│                                                         │
│ Shows:                                                  │
│ • Project is 65% complete (from last session)          │
│ • 13 tasks done, 7 outstanding                         │
│ • Current plan: Agentic kernel integration             │
│ • Last blockers: Waiting on Gemini API quota           │
│ • Recent work: Implemented consensus voting            │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│ Ask Claude:                                             │
│ "Based on the project status, what should I work on?"  │
│                                                         │
│ Claude sees:                                            │
│ • 65% complete with specific blockers                  │
│ • Recent work direction                                │
│ • Context window available (32%)                       │
│ • Can make informed suggestions                        │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│ WORK & ITERATE                                          │
│ • Statusline shows real-time context consumption       │
│ • You make progress on outstanding tasks               │
└─────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────┐
│ Run /project-progress OS-App update                     │
│                                                         │
│ Log:                                                    │
│ • New completion %                                     │
│ • Tasks completed/outstanding                          │
│ • Summary of work done                                 │
│ • Any new blockers                                     │
└─────────────────────────────────────────────────────────┘
```

---

## Files & Locations

### Skills
- `~/.claude/skills/project-progress.sh` - Project tracking skill
- `~/.claude/scripts/statusline-create.sh` - Metric generator
- `~/.claude/statusline-command.sh` - Context window display (auto-integrated)

### Documentation
- `~/.claude/skills/project-progress-README.md` - Project skill details
- `~/.claude/SKILL-GUIDE.md` - This file

### Data
- `~/.claude/projects/[project]/progress.json` - Project tracking data
- `~/.claude/tmp/statusline-cache` - Performance cache
- `~/.claude/tmp/statusline-[metric]-cache` - Per-metric caches

### Configuration
- `~/.claude/settings.json` - Statusline integration (already configured)

---

## Use Cases & Examples

### Use Case 1: Resume Long-Running Project
```bash
# You paused OS-App to work on something else
# New session, you want to jump back in

$ /project-progress OS-App
# See: 65% complete, 7 tasks outstanding, blockers

$ # Ask Claude: "What's the most impactful next step given the blockers?"
```

### Use Case 2: Track Multiple Projects
```bash
# Manage OS-App, CareerCoach, and researchgravity simultaneously

$ /project-progress
# Quick overview of all 3 projects

# Work on whichever has priority or is unblocked

$ /project-progress [project] update
# Log progress on each
```

### Use Case 3: Create Custom Metrics
```bash
# You want to track cache efficiency, not just context window

$ bash ~/.claude/scripts/statusline-create.sh

# Follow prompts to create a cache-efficiency statusline
# Generates: ~/.claude/statusline-cache-efficiency.sh

# Add to settings.json for continuous display
```

### Use Case 4: Daily Standup
```bash
# Start of day, see what's in flight

$ /project-progress

# See all projects, statuses, recent activity
# Prioritize based on blockers, completion %
# Tell stakeholders: "OS-App 65%, blocked on X; CareerCoach 32%, making progress"
```

---

## Advanced: Creating Custom Progress Metrics

Use the statusline generator to create displays for:
- Daily token budget remaining
- Cache hit rate
- Session window position
- Model capacity usage
- Cost tracking
- Any custom metric from any data source

```bash
# Interactive setup
bash ~/.claude/scripts/statusline-create.sh

# Or manually create scripts following the pattern
# See generated scripts for examples
```

---

## Future Enhancements

### Potential V2.0 Features
- Auto-detect progress from git commit messages (`#65%`, `[task: 4/8]`)
- Burndown charts (show task completion rate over time)
- Integration with task list system
- Milestone notifications (celebrate when hitting 50%, 75%, 100%)
- Cross-project dependency tracking
- Weekly progress reports with trends
- Compare project pace (velocity)

### Integration Possibilities
- Slack integration: Daily standup summaries
- Dashboard: Web view of all projects
- Notifications: Alert when blocker added, milestone reached
- Export: CSV/JSON reports for stakeholders

---

## Command Reference

### /project-progress (Project Tracker)

```bash
# List all projects
/project-progress

# Setup new project
/project-progress [project-name] setup

# View status (default)
/project-progress [project-name]
/project-progress [project-name] status

# Interactive update
/project-progress [project-name] update

# Show help
/project-progress --help
/project-progress help
```

### /statusline-create (Metric Generator)

```bash
# Interactive setup
bash ~/.claude/scripts/statusline-create.sh

# Run generated script
bash ~/.claude/statusline-[metric-slug].sh

# Test with data
echo '{"data": 42}' | bash ~/.claude/statusline-[metric-slug].sh
```

---

## Troubleshooting

### "Project not found"
- Run: `/project-progress [project] setup` to create it

### "Git activity not showing"
- Ensure .git directory exists in project root
- Check git is installed: `which git`

### "Progress not updating"
- Run: `/project-progress [project] update` to manually log progress
- Check file permissions on `~/.claude/projects/[project]/`

### Statusline not showing
- Check `~/.claude/settings.json` has statusLine configured
- Verify `~/.claude/statusline-command.sh` is executable
- Ensure jq is installed: `which jq`

---

## Tips & Best Practices

1. **Session Start**: Run `/project-progress` to see what's in flight
2. **Session End**: Run `/project-progress [project] update` to log your work
3. **Blockers**: Always log them so next session you remember context
4. **Plans**: Set plan title & summary - helps Claude understand context
5. **Regular Updates**: Even brief updates are valuable for continuity

---

**Last Updated**: 2026-01-25
**Skills Status**: ✅ Active
**Data**: `~/.claude/projects/`
