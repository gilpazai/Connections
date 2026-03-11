#!/bin/bash

# Script to commit and push code changes
# This script stages modified files and creates a commit with appropriate message

set -e

echo "📦 Starting commit and push process..."
echo ""

# Show current status
echo "Current git status:"
git status --short
echo ""

# Stage modified files (exclude the local settings file)
echo "📝 Staging files..."
git add -A
git reset .claude/settings.local.json 2>/dev/null || true

echo ""
echo "Files to be committed:"
git diff --cached --name-only
echo ""

# Create commit with detailed message
echo "💾 Creating commit..."
git commit -m "$(cat <<'EOF'
Add OpenAI model selection and pricing display to Settings

- Expand OpenAI model options: gpt-4o-mini, gpt-4o, gpt-4-turbo, gpt-3.5-turbo
- Add pricing constants with input/output costs per 1M tokens for each model
- Add estimated token usage per enrichment (7000 input + 1500 output)
- Implement dynamic Pricing & Token Usage section in LLM & Enrichment tab
- Display 3 metrics: tokens per enrichment, cost per enrichment, cost per 50 people
- Add model comparison table with pricing breakdown for all 4 models
- Include speed indicators and recommendation for gpt-4o-mini

The pricing section displays real-time cost estimates based on selected model,
helping users make informed decisions about model selection based on budget
and quality tradeoffs.

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"

echo ""
echo "✅ Commit created successfully!"
echo ""

# Show the commit
echo "Latest commit:"
git log --oneline -1
echo ""

# Push to remote
echo "🚀 Pushing to remote..."
git push origin HEAD

echo ""
echo "✨ Successfully committed and pushed changes!"
