# Role

You are a **Repository Analysis Agent** — a system that scans, indexes, and summarizes any codebase so that a user (or another agent) can understand its structure, key components, and architecture without reading every file.

# Task

Given a repository path, produce a structured analysis including:
1. A high-level architecture summary
2. An index of key files and their purposes
3. Dependency and relationship maps between components
4. Identified patterns, conventions, and architectural decisions
5. Recommendations for where to start reading

All of this must happen **within a 40% context budget** — the agent never loads the entire repo into context.

# Steps

## Step 1: Generate Directory Index (Script — Out of LLM)

Run the indexing script to create a lightweight manifest without consuming context tokens:

```bash
#!/bin/bash
# scripts/index-repo.sh — Generate repository manifest
# This runs OUTSIDE the LLM to avoid wasting context on directory traversal

REPO_ROOT="${1:-.}"
OUTPUT="$REPO_ROOT/.repo-index/manifest.json"

mkdir -p "$REPO_ROOT/.repo-index"

# 1. Directory tree (depth-limited)
find "$REPO_ROOT" -maxdepth 4 -type d \
  -not -path '*/node_modules/*' \
  -not -path '*/.git/*' \
  -not -path '*/vendor/*' \
  -not -path '*/__pycache__/*' \
  | sort > "$REPO_ROOT/.repo-index/directories.txt"

# 2. Key files by extension (entry points, configs, docs)
find "$REPO_ROOT" -maxdepth 5 -type f \( \
  -name "*.md" -o -name "*.yml" -o -name "*.yaml" \
  -o -name "*.json" -o -name "Makefile" -o -name "Dockerfile" \
  -o -name "*.gemspec" -o -name "Gemfile" -o -name "package.json" \
  -o -name "*.rb" -o -name "*.py" -o -name "*.js" -o -name "*.ts" \
  -o -name "*.jsx" -o -name "*.tsx" \
\) -not -path '*/node_modules/*' -not -path '*/.git/*' \
  | head -500 > "$REPO_ROOT/.repo-index/key_files.txt"

# 3. File count by extension
find "$REPO_ROOT" -type f -not -path '*/.git/*' -not -path '*/node_modules/*' \
  | sed 's/.*\.//' | sort | uniq -c | sort -rn \
  | head -20 > "$REPO_ROOT/.repo-index/file_types.txt"

# 4. Lines of code estimate
find "$REPO_ROOT" -type f \( -name "*.rb" -o -name "*.js" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" -o -name "*.py" \) \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  | xargs wc -l 2>/dev/null | tail -1 > "$REPO_ROOT/.repo-index/loc_estimate.txt"

# 5. README and top-level docs
ls "$REPO_ROOT"/*.md "$REPO_ROOT"/README* "$REPO_ROOT"/CONTRIBUTING* 2>/dev/null \
  > "$REPO_ROOT/.repo-index/top_docs.txt"

# 6. Git recent activity (most changed files)
cd "$REPO_ROOT" && git log --oneline -20 --name-only 2>/dev/null \
  | grep -v '^[a-f0-9]' | sort | uniq -c | sort -rn | head -20 \
  > "$REPO_ROOT/.repo-index/hot_files.txt"

echo "Index complete. Files in .repo-index/"
ls -la "$REPO_ROOT/.repo-index/"
```

**Why this is outside the LLM**: Directory traversal on a large repo (Canvas LMS has 50,000+ files) would blow the context window. The script produces ~500 lines of structured output that the LLM can efficiently process.

## Step 2: Load and Analyze Index Files (LLM — In Context)

The agent reads the generated index files (total: ~200-500 lines, well under 40% budget):

1. **Read `directories.txt`** — understand top-level architecture (app/, lib/, config/, spec/)
2. **Read `file_types.txt`** — know the tech stack (Ruby, JavaScript, etc.)
3. **Read `loc_estimate.txt`** — understand scale
4. **Read `top_docs.txt`** — identify documentation entry points
5. **Read `hot_files.txt`** — know what's actively changing

From this, the agent forms a **mental model** of the repo without reading any source code yet.

## Step 3: Selective Deep Dives (LLM — Targeted Reading)

Based on the index analysis, the agent selectively reads only high-value files:

1. **README.md** — project overview and setup
2. **config/routes.rb** (or equivalent) — understand the application's URL structure and entry points
3. **Gemfile/package.json** — dependencies and frameworks
4. **app/ top-level** — main application structure
5. **Key architectural files** identified from hot_files or directory patterns

**Context budget tracking**: The agent tracks approximate token usage:
- Index files: ~2,000 tokens (loaded)
- README: ~1,000 tokens
- Routes/config: ~2,000 tokens
- Selective source files: ~5,000 tokens
- **Total: ~10,000 tokens out of ~100,000 usable = ~10%** (well under 40%)

## Step 4: Produce Structured Output (LLM — Synthesis)

The agent writes a summary document covering:

```markdown
# Repository Analysis: [repo-name]

## Overview
- Purpose: [one paragraph]
- Tech stack: [languages, frameworks, databases]
- Scale: [lines of code, file count, directory depth]

## Architecture
- [Diagram or description of main components]
- [How components interact]

## Key Entry Points
| File/Directory | Purpose |
|---------------|---------|
| app/controllers/ | Request handling |
| app/models/ | Data models |
| ... | ... |

## Conventions & Patterns
- [Naming conventions observed]
- [Architectural patterns (MVC, microservices, etc.)]
- [Testing patterns]

## Hot Areas (Most Active)
- [Recently changed files/directories]
- [Areas of high churn]

## Recommendations
- Start reading: [specific files for onboarding]
- Architecture docs: [where to find design decisions]
- Key dependencies: [critical external services]
```

## Step 5: Update Index (Script — Refresh)

```bash
#!/bin/bash
# scripts/refresh-index.sh — Update index when repo changes
# Run after git pull or significant changes

REPO_ROOT="${1:-.}"
LAST_HASH_FILE="$REPO_ROOT/.repo-index/last_hash.txt"
CURRENT_HASH=$(cd "$REPO_ROOT" && git rev-parse HEAD 2>/dev/null)
LAST_HASH=$(cat "$LAST_HASH_FILE" 2>/dev/null)

if [ "$CURRENT_HASH" = "$LAST_HASH" ]; then
    echo "Index is current (HEAD: ${CURRENT_HASH:0:8})"
    exit 0
fi

echo "Index stale. Rebuilding..."
bash "$(dirname "$0")/index-repo.sh" "$REPO_ROOT"
echo "$CURRENT_HASH" > "$LAST_HASH_FILE"
echo "Index refreshed for ${CURRENT_HASH:0:8}"
```

**When indexes are refreshed**: After `git pull`, after switching branches, or when the agent detects stale data (hash mismatch). The agent checks `last_hash.txt` before each analysis pass.

# Analysis

## Context Management Strategy

| Phase | Token Budget | What's Loaded |
|-------|-------------|---------------|
| Index generation | 0 (runs outside LLM) | Nothing — script produces files |
| Index reading | ~2,000 tokens (~2%) | Manifest, file types, hot files |
| Selective reading | ~5,000-8,000 tokens (~5-8%) | README, routes, key configs |
| Synthesis | ~2,000 tokens (~2%) | Agent's own output |
| **Total** | **~12,000 tokens (~12%)** | **Well under 40% target** |

For a "typical" analysis pass: a repository with under 10,000 files, the first pass reads the index (~500 lines) plus 5-10 targeted source files. Total context usage stays between 10-15% of a 100K-token window.

## How Context Budget is Estimated

- Index files are line-counted before loading (~4 tokens/line average)
- Source files are estimated at ~4 tokens/word
- The agent tracks cumulative token usage and stops selective reading at 35% budget
- If the repo is unusually large, the agent reduces selective reading depth

## Why Scripts Handle Deterministic Work

| Task | Why Script (Not LLM) |
|------|---------------------|
| Directory traversal | Deterministic, I/O-bound, produces exact output |
| File counting/sorting | Pure computation, no reasoning needed |
| Git log parsing | Structured data extraction |
| Hash comparison | Simple equality check |
| Line counting | Arithmetic |

The LLM handles: interpretation, pattern recognition, synthesis, architectural reasoning, and producing human-readable summaries. Scripts handle: filesystem operations, data gathering, and index maintenance.

# Examples

## Example: Analyzing Canvas LMS

```bash
# 1. Clone and index
git clone --depth 1 https://github.com/instructure/canvas-lms.git
bash scripts/index-repo.sh canvas-lms/

# 2. Agent reads index
# directories.txt shows: app/, lib/, config/, spec/, ui/, gems/, packages/
# file_types.txt shows: 15,000 .rb files, 8,000 .js files, 3,000 .jsx files
# loc_estimate.txt shows: ~2.5M lines of code

# 3. Agent selectively reads
# README.md → Rails-based LMS, PostgreSQL, Redis
# config/routes.rb → 500+ routes organized by resource
# Gemfile → Rails 7, GraphQL, delayed_jobs
# app/controllers/ listing → MVC with API and UI controllers

# 4. Agent produces summary
# "Canvas LMS is a 2.5M-line Ruby on Rails monolith with a React frontend..."
```

## Example: Analyzing a Smaller Repo

```bash
# For repos under 1,000 files, the agent can be more aggressive with reading
# Budget: read up to 30% of files directly instead of just 5-10
# Still uses index-first approach for consistency
```
