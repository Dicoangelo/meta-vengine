#!/bin/bash
# Username Check - Ensures correct GitHub username at session start
# Fixes: 112 git errors from case sensitivity

CORRECT_USERNAME="Dicoangelo"
REPOS=(~/OS-App ~/CareerCoachAntigravity ~/researchgravity ~/.agent-core ~/The-Decosystem ~/Metaventions-AI-Landing)

fixed=0
for repo in "${REPOS[@]}"; do
    if [ -d "$repo/.git" ]; then
        remote_url=$(git -C "$repo" remote get-url origin 2>/dev/null)
        if echo "$remote_url" | grep -qi "github.com/dicoangelo" && ! echo "$remote_url" | grep -q "$CORRECT_USERNAME"; then
            # Fix it silently
            fixed_url=$(echo "$remote_url" | sed "s/github.com\/[dD]icoangelo/github.com\/$CORRECT_USERNAME/gi")
            git -C "$repo" remote set-url origin "$fixed_url" 2>/dev/null
            ((fixed++))
        fi
    fi
done

if [ $fixed -gt 0 ]; then
    echo "username-check: Fixed $fixed repo(s) with wrong GitHub username"
fi
