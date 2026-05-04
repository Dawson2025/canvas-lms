# Canvas Content Access — Agent Context Document

## Purpose

This document gives an AI agent everything it needs to query Canvas course content directly — either via the live database (fork model) or via the REST API (extension model). No sync scripts, no file export, no MCP tools. Just knowledge + one general tool (Bash).

---

## How Canvas Stores Course Content

All course content lives in a PostgreSQL database. Content is HTML text stored in specific columns. The module system uses a polymorphic join table (`content_tags`) to organize content into ordered sequences.

### Core Tables

| Table | What It Stores | Key Content Column | Key Filter |
|-------|---------------|-------------------|-----------|
| `courses` | Course metadata + syllabus | `syllabus_body` (HTML) | `id` |
| `assignments` | Assignment descriptions + dates | `description` (HTML), `due_at`, `points_possible` | `context_id` = course_id, `workflow_state = 'published'` |
| `wiki_pages` | Page content | `body` (HTML), `title`, `url` (slug) | `wiki_id` (get from `wikis` table where `context_id` = course_id) |
| `discussion_topics` | Discussions + announcements | `message` (HTML), `title` | `context_id`, filter `type = 'Announcement'` for announcements |
| `context_modules` | Module structure | `name`, `position`, `prerequisites` (serialized) | `context_id`, `workflow_state = 'active'` |
| `content_tags` | Module items (polymorphic links) | `content_type`, `content_id`, `position`, `title` | `context_module_id`, `workflow_state = 'active'` |
| `attachments` | Files | `filename`, `display_name`, `content_type` | `context_id`, `context_type = 'Course'`, `file_state = 'available'` |

### The ContentTag Polymorphic Pattern

Module items link to content via `content_tags.content_type` + `content_tags.content_id`:

| content_type | Points To | How To Fetch |
|-------------|-----------|-------------|
| `Assignment` | `assignments` table | `Assignment.find(content_id)` |
| `WikiPage` | `wiki_pages` table | `WikiPage.find(content_id)` |
| `DiscussionTopic` | `discussion_topics` table | `DiscussionTopic.find(content_id)` |
| `Attachment` | `attachments` table | `Attachment.find(content_id)` |
| `Quizzes::Quiz` | `quizzes` table | `Quizzes::Quiz.find(content_id)` |
| `ContextModuleSubHeader` | No table — title only | Use `content_tags.title` directly |
| `ExternalUrl` | No table — URL only | Use `content_tags.url` directly |
| `ContextExternalTool` | `context_external_tools` | LTI tool launch |

---

## Method 1: Rails Runner (Fork Model — Direct DB Access)

Use `bin/rails runner` to execute Ruby against the live Canvas database. Read-only queries only.

### Get everything for a course (one command)

```bash
bin/rails runner '
  course = Course.find(COURSE_ID)

  puts "# #{course.name}\n"
  puts "## Syllabus\n#{course.syllabus_body}\n"

  puts "## Modules"
  course.context_modules.active.ordered.each do |mod|
    puts "\n### #{mod.name} (position: #{mod.position})"
    if mod.prerequisites.any?
      puts "Prerequisites: #{mod.prerequisites.map { |p| p[:name] }.join(", ")}"
    end
    mod.content_tags.active.order(:position).each do |tag|
      case tag.content_type
      when "Assignment"
        a = tag.content
        puts "  - [Assignment] #{a.title} | due: #{a.due_at} | #{a.points_possible} pts"
      when "WikiPage"
        puts "  - [Page] #{tag.content.title}"
      when "DiscussionTopic"
        puts "  - [Discussion] #{tag.content.title}"
      when "Attachment"
        puts "  - [File] #{tag.content.display_name}"
      when "ContextModuleSubHeader"
        puts "  - [Header] #{tag.title}"
      when "ExternalUrl"
        puts "  - [Link] #{tag.title} → #{tag.url}"
      end
    end
  end

  puts "\n## Announcements"
  course.announcements.active.order(posted_at: :desc).limit(10).each do |a|
    puts "- #{a.title} (#{a.posted_at&.strftime("%Y-%m-%d")})"
  end
'
```

### Common queries

```bash
# Assignments due this week
bin/rails runner '
  Course.find(COURSE_ID).assignments.published
    .where(due_at: Time.current..1.week.from_now)
    .order(:due_at)
    .each { |a| puts "#{a.due_at.strftime("%m/%d")} | #{a.title} | #{a.points_possible} pts" }
'

# Search page content
bin/rails runner '
  Course.find(COURSE_ID).wiki_pages.published
    .where("body ILIKE ?", "%SEARCH_TERM%")
    .each { |p| puts "#{p.title}: #{p.url}" }
'

# Module prerequisites chain
bin/rails runner '
  Course.find(COURSE_ID).context_modules.active.ordered.each do |m|
    prereqs = m.prerequisites.map { |p| p[:name] }.join(", ")
    puts "#{m.name} → requires: #{prereqs.presence || "none"}"
  end
'

# Get full assignment with rubric
bin/rails runner '
  a = Assignment.find(ASSIGNMENT_ID)
  puts "# #{a.title}\n\n#{a.description}\n\nDue: #{a.due_at}\nPoints: #{a.points_possible}"
  if a.rubric
    puts "\n## Rubric"
    a.rubric.criteria.each { |c| puts "- #{c[:description]} (#{c[:points]} pts)" }
  end
'

# FERPA-safe: only published content
bin/rails runner '
  # All these scopes filter unpublished automatically:
  # .published (assignments, wiki_pages)
  # .active (context_modules, content_tags, discussion_topics)
  # .available (attachments via file_state)
'
```

---

## Method 2: Canvas REST API (Extension Model — Any Canvas)

Use `curl` or a thin CLI wrapper. Requires an API token.

### Setup

```bash
export CANVAS_URL="https://your-school.instructure.com"
export CANVAS_TOKEN="your-api-token"

# Helper function
canvas-api() {
  curl -s -H "Authorization: Bearer $CANVAS_TOKEN" "$CANVAS_URL/api/v1/$1"
}
```

### Common queries

```bash
# Course info + syllabus
canvas-api "courses/COURSE_ID?include[]=syllabus_body" | jq '{name, syllabus_body}'

# All published assignments with dates
canvas-api "courses/COURSE_ID/assignments?order_by=due_at&per_page=100" | \
  jq '.[] | {title, due_at, points_possible, html_url}'

# Module structure with items
canvas-api "courses/COURSE_ID/modules?include[]=items&per_page=100" | \
  jq '.[] | {name, position, items: [.items[]? | {title, type, content_id}]}'

# Search pages
canvas-api "courses/COURSE_ID/pages?search_term=QUERY&per_page=50" | \
  jq '.[] | {title, url}'

# Get page content
canvas-api "courses/COURSE_ID/pages/PAGE_URL" | jq '{title, body}'

# Announcements
canvas-api "courses/COURSE_ID/discussion_topics?only_announcements=true&per_page=20" | \
  jq '.[] | {title, message, posted_at}'

# Files list
canvas-api "courses/COURSE_ID/files?per_page=100" | \
  jq '.[] | {display_name, size, content_type, url}'
```

### Pagination

Canvas paginates at 100 items max. Check for `Link` header with `rel="next"`:

```bash
# Follow pagination
canvas-api-all() {
  local url="$1"
  while [ -n "$url" ]; do
    response=$(curl -sD- -H "Authorization: Bearer $CANVAS_TOKEN" "$url")
    echo "$response" | sed '1,/^\r$/d'  # body
    url=$(echo "$response" | grep -o '<[^>]*>; rel="next"' | grep -o 'http[^>]*')
  done
}
```

---

## Method 3: Hybrid — Query Live + Cache Locally

Best of both: query the source for fresh data, cache results as markdown for deep analysis.

```bash
# Agent flow:
# 1. Quick query for structure (live)
canvas-api "courses/COURSE_ID/modules?include[]=items" > /tmp/modules.json

# 2. Agent reads JSON, identifies what it needs

# 3. Fetch specific content (live)
canvas-api "courses/COURSE_ID/pages/instruction-3-1" | jq -r '.body' > /tmp/page.html

# 4. Convert for reading (deterministic)
pandoc /tmp/page.html -t markdown -o /tmp/page.md

# 5. Agent reads the markdown
cat /tmp/page.md
```

No persistent filesystem, no sync script. Just query → cache → read → discard.

---

## What the Agent Needs in Its Context

For an agent to use any of these methods effectively, it needs this document (or a distilled version) in its system prompt or loadable via trigger. The key context is:

1. **Which method to use** (Rails runner vs API vs hybrid — depends on deployment)
2. **The table/endpoint map** (which table or endpoint has what content)
3. **The ContentTag polymorphic pattern** (how modules link to content)
4. **FERPA scopes** (always filter by published/active/available)
5. **Common query patterns** (copy-paste-modify templates above)

Total context cost: ~200 lines of markdown. Loaded on demand via trigger, not in system prompt.
