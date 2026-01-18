---
description: Generate and save session summary to SESSION_LOG.md
allowed-tools: [Read, Write, Bash]
---

# Session Logger

Generate a checkpoint summary and save it to the project's SESSION_LOG.md file.

## Steps

1. Generate a summary of this session:
   - What was accomplished
   - Files changed/created
   - Current state
   - Next steps

2. Get the current date and time using bash

3. Append to SESSION_LOG.md in the current working directory:

```markdown
---

## YYYY-MM-DD @ HH:MM

**What was done:**
- Item 1
- Item 2

**Files changed:**
- path/to/file1
- path/to/file2

**Next steps:**
- Next task 1
- Next task 2
```

4. If SESSION_LOG.md doesn't exist, create it first with a header

5. Confirm to user:
```
Session logged to SESSION_LOG.md
Safe to /quit or /clear now.
```
