---
name: save
description: Auto-save session summary before ending
---

# Session Logger

When the user runs `/save`, automatically generate and save a session summary.

## Steps

1. **Generate a summary** of this session:
   - What was accomplished
   - Files changed/created
   - Current state
   - Next steps

2. **Detect the project directory** from the current working directory

3. **Append to SESSION_LOG.md** using this bash command:
```bash
cat >> "$(pwd)/SESSION_LOG.md" << 'SUMMARY'

---

## [DATE] @ [TIME]

**What was done:**
- [bullet points]

**Files changed:**
- [list]

**Next steps:**
- [list]

SUMMARY
```

4. **Update CURRENT_TASK.md** if it exists:
```bash
# Update the "Active Focus" section with next steps
```

5. **Confirm to user:**
```
Session logged to SESSION_LOG.md
Updated CURRENT_TASK.md

Safe to /quit or /clear now.
```

## If No SESSION_LOG.md Exists

Create one first:
```bash
echo "# Session Log\n\n" > "$(pwd)/SESSION_LOG.md"
```

Then append the summary.

## Format

Use this exact format for the log entry:

```markdown
---

## YYYY-MM-DD @ HH:MM

**What was done:**
- Item 1
- Item 2

**Files changed:**
- path/to/file1
- path/to/file2

**Current state:**
Brief description

**Next steps:**
- Next task 1
- Next task 2
```
