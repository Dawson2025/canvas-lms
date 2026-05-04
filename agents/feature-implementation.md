# Feature Implementation Agent

## Role and Non-Goals

**Role**: Implementation agent that takes scoped work items from the GitHub Project board and implements them in the Canvas LMS fork, following the feature research and project plan.

**Non-goals**: This agent does NOT invent scope, does NOT push to protected branches directly, and does NOT hand-author large implementation code — it proposes changes, the human reviews diffs and approves merges.

## Inputs (Lab 2.1 + 2.2 Artifacts)

| Input | Path | Purpose |
|-------|------|---------|
| Feature brief | `agents/tasks/feature-1/feature-1.md` | Problem statement, architecture, scope |
| Implementation research | `agents/tasks/feature-1/implementation-research.md` | FRs, NFRs, codebase analysis, testing plan |
| Project creation agent | `agents/project-creation.md` | How project items were derived from research |
| GitHub Project | [Dawson2025/projects/2](https://github.com/users/Dawson2025/projects/2) | 19 work items with Priority, Phase, Type fields |

## Locating the GitHub Project and Items

- **Project number**: 2
- **Owner**: Dawson2025
- **Repo**: Dawson2025/canvas-lms
- **List items**: `gh project item-list 2 --owner Dawson2025 --format json`
- **Find specific item**: Match by title string from the project board

## Procedure

### Step 1: Select Work Item

Choose a work item from the GitHub Project that:
1. Has status "Todo" (not already In Progress or Done)
2. Matches in-scope work from `implementation-research.md` — not invented scope
3. Has no unresolved dependencies (check story body for dependency notes)
4. Prioritize P0 items first, then P1

```bash
gh project item-list 2 --owner Dawson2025 --format json | jq '.items[] | select(.status == "Todo") | {title, status}'
```

### Step 2: Move to In Progress via MCP (gh CLI)

When you are actively implementing — not before:

```bash
# Get the item ID for the selected work item
gh project item-list 2 --owner Dawson2025 --format json | jq '.items[] | select(.title | contains("ITEM_TITLE")) | .id'

# Move to In Progress
gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <STATUS_FIELD_ID> --single-select-option-id <IN_PROGRESS_OPTION_ID>
```

If field/option IDs are unknown, discover them:
```bash
gh project field-list 2 --owner Dawson2025 --format json
```

**If MCP/gh is temporarily unavailable**: Log the intended status change in `agents/tasks/feature-1/implementation-evidence.md` with timestamp, and update the board manually as soon as access is restored.

### Step 3: Create Feature Branch

```bash
git checkout -b feature/ITEM-SHORT-NAME master
```

Branch naming convention: `feature/<short-description>` (e.g., `feature/content-directory-reader`).

### Step 4: Implementation Session

Use the implementation agent (AI tool) to propose and apply changes:
1. Reference the specific codebase findings from `implementation-research.md` Section 4
2. Keep changes small and reviewable — prefer multiple small PRs over one large one
3. Run any relevant checks your stack supports (linting, type checks, existing tests)
4. Verify the change works locally before opening a PR

### Step 5: Open Pull Request

```bash
gh pr create --repo Dawson2025/canvas-lms \
  --title "feat: <short description tied to work item>" \
  --body "## Work Item
<title from GitHub Project>

## Changes
<bullet list of what changed>

## Plan Trace
Maps to FR-N / NFR-N from implementation-research.md.
Derived from project item #N on the GitHub Project board.

## Testing
<what was verified>"
```

PR must clearly relate to the work item — by title, description, or linked issue.

### Step 6: Review and Merge

After human review:
```bash
# Merge the PR (human approves)
gh pr merge <PR_NUMBER> --repo Dawson2025/canvas-lms --squash

# Switch back to master and pull
git checkout master && git pull
```

### Step 7: Mark Complete on Board

After merge is confirmed:
```bash
gh project item-edit --project-id <PROJECT_ID> --id <ITEM_ID> --field-id <STATUS_FIELD_ID> --single-select-option-id <DONE_OPTION_ID>
```

## MCP: Tools and Patterns

This agent uses `gh` CLI (GitHub's official CLI) for all GitHub operations — same toolset as Lab 2.2's project-creation agent. No separate GitHub MCP Server needed.

| Operation | Command |
|-----------|---------|
| List project items | `gh project item-list 2 --owner Dawson2025` |
| Move item status | `gh project item-edit --project-id ... --id ... --field-id ... --single-select-option-id ...` |
| Create PR | `gh pr create --repo Dawson2025/canvas-lms` |
| Merge PR | `gh pr merge <N> --repo Dawson2025/canvas-lms --squash` |
| View PR | `gh pr view <N> --repo Dawson2025/canvas-lms` |

**Board column mapping**: Status field uses GitHub Projects V2 default statuses:
- "Todo" = not started
- "In Progress" = actively implementing
- "Done" = merged and verified

## Guardrails

1. **No secrets**: Never commit tokens, API keys, or credentials to any tracked file
2. **No surprise scope**: Every change must trace to a work item from the project board, which traces to `implementation-research.md`
3. **No direct push to master**: All changes go through feature branches and pull requests
4. **Small PRs**: Prefer incremental, reviewable changes over monolithic PRs
5. **Scope deviations documented**: If you must deviate from the plan, add a rationale in the PR description — never silent drift

## Verification Before Complete

Before marking a work item as "Done":
1. PR is merged (link in evidence doc)
2. Code is on the target branch (master)
3. Any applicable tests pass (or test plan noted for Lab 4.1)
4. The change demonstrably addresses the work item's acceptance criteria
5. Board status updated via gh CLI

## Failure Modes

| Situation | Response |
|-----------|----------|
| gh CLI auth fails | Use `gh auth login` to re-authenticate; log the gap in evidence doc |
| Board field IDs change | Re-discover with `gh project field-list 2 --owner Dawson2025 --format json` |
| PR blocked by CI | Fix the issue or document the blocker; don't force-merge |
| Scope larger than expected | Split into smaller items; create new project items for the remaining work |
| MCP unavailable | Log intended actions manually; update board when restored |
