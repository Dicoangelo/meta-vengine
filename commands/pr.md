# Create Pull Request

Analyze all changes since branching from main, then create a well-documented PR.

## Steps
1. Run `git diff main...HEAD` to see all changes
2. Run `git log main..HEAD --oneline` for commit history
3. Identify the type: feature, bugfix, refactor, docs
4. Create PR with:
   - Clear title (conventional commit style)
   - Summary of what changed and WHY
   - Testing notes
   - Any breaking changes

$ARGUMENTS
