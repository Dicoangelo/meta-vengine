#!/bin/bash
# Subscription Value Tracker - Quick CLI
# Usage: cval [report|json]

cd ~/.claude/kernel
node subscription-tracker.js "${1:-report}"
