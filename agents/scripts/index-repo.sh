#!/bin/bash
# scripts/index-repo.sh — Generate repository manifest
REPO_ROOT="${1:-.}"
OUTPUT_DIR="$REPO_ROOT/.repo-index"
mkdir -p "$OUTPUT_DIR"

find "$REPO_ROOT" -maxdepth 4 -type d \
  -not -path '*/node_modules/*' -not -path '*/.git/*' \
  -not -path '*/vendor/*' -not -path '*/__pycache__/*' \
  | sort > "$OUTPUT_DIR/directories.txt"

find "$REPO_ROOT" -maxdepth 5 -type f \( \
  -name "*.md" -o -name "*.yml" -o -name "*.yaml" \
  -o -name "*.json" -o -name "Makefile" -o -name "Dockerfile" \
  -o -name "*.gemspec" -o -name "Gemfile" -o -name "package.json" \
  -o -name "*.rb" -o -name "*.py" -o -name "*.js" -o -name "*.ts" \
\) -not -path '*/node_modules/*' -not -path '*/.git/*' \
  | head -500 > "$OUTPUT_DIR/key_files.txt"

find "$REPO_ROOT" -type f -not -path '*/.git/*' -not -path '*/node_modules/*' \
  | sed 's/.*\.//' | sort | uniq -c | sort -rn \
  | head -20 > "$OUTPUT_DIR/file_types.txt"

ls "$REPO_ROOT"/*.md "$REPO_ROOT"/README* 2>/dev/null > "$OUTPUT_DIR/top_docs.txt"

cd "$REPO_ROOT" && git log --oneline -20 --name-only 2>/dev/null \
  | grep -v '^[a-f0-9]' | sort | uniq -c | sort -rn | head -20 \
  > "$OUTPUT_DIR/hot_files.txt"

echo "Index complete: $OUTPUT_DIR/"
ls "$OUTPUT_DIR/"
