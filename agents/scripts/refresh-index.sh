#!/bin/bash
# scripts/refresh-index.sh — Update index when repo changes
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
