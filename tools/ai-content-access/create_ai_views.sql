-- Canvas AI Content Access — PostgreSQL Views
-- These views make course content accessible to AI agents with:
-- 1. FERPA-safe filtering (only published/active content)
-- 2. HTML→plaintext conversion (strips tags for agent readability)
-- 3. Pre-joined tables (no agent SQL composition needed for common queries)
--
-- For the fork model, this runs as a Rails migration.
-- For testing, run directly against PostgreSQL.

-- ============================================================
-- UTILITY: Simple HTML tag stripper
-- A real deployment would use a proper HTML→Markdown converter.
-- This basic version strips tags for testing the view pattern.
-- ============================================================

CREATE OR REPLACE FUNCTION strip_html_tags(html TEXT)
RETURNS TEXT AS $$
BEGIN
  IF html IS NULL THEN RETURN NULL; END IF;
  -- Remove script/style blocks entirely
  html := regexp_replace(html, '<script[^>]*>.*?</script>', '', 'gis');
  html := regexp_replace(html, '<style[^>]*>.*?</style>', '', 'gis');
  -- Convert common elements to markdown-ish text
  html := regexp_replace(html, '<h1[^>]*>', E'\n# ', 'gi');
  html := regexp_replace(html, '<h2[^>]*>', E'\n## ', 'gi');
  html := regexp_replace(html, '<h3[^>]*>', E'\n### ', 'gi');
  html := regexp_replace(html, '</h[1-6]>', E'\n', 'gi');
  html := regexp_replace(html, '<li[^>]*>', E'\n- ', 'gi');
  html := regexp_replace(html, '<br\s*/?>', E'\n', 'gi');
  html := regexp_replace(html, '<p[^>]*>', E'\n', 'gi');
  html := regexp_replace(html, '</p>', '', 'gi');
  html := regexp_replace(html, '<strong[^>]*>', '**', 'gi');
  html := regexp_replace(html, '</strong>', '**', 'gi');
  html := regexp_replace(html, '<em[^>]*>', '*', 'gi');
  html := regexp_replace(html, '</em>', '*', 'gi');
  html := regexp_replace(html, '<code[^>]*>', '`', 'gi');
  html := regexp_replace(html, '</code>', '`', 'gi');
  html := regexp_replace(html, '<td[^>]*>', ' | ', 'gi');
  html := regexp_replace(html, '<tr[^>]*>', E'\n', 'gi');
  html := regexp_replace(html, '<th[^>]*>', ' | **', 'gi');
  html := regexp_replace(html, '</th>', '** ', 'gi');
  -- Strip remaining tags
  html := regexp_replace(html, '<[^>]+>', '', 'g');
  -- Decode common entities
  html := replace(html, '&amp;', '&');
  html := replace(html, '&lt;', '<');
  html := replace(html, '&gt;', '>');
  html := replace(html, '&quot;', '"');
  html := replace(html, '&#39;', '''');
  html := replace(html, '&nbsp;', ' ');
  -- Clean up excessive whitespace
  html := regexp_replace(html, E'\n{3,}', E'\n\n', 'g');
  html := trim(html);
  RETURN html;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ============================================================
-- AI VIEWS — Pre-made queries for common agent access patterns
-- ============================================================

-- All published assignments for a course, FERPA-safe
CREATE OR REPLACE VIEW ai_course_assignments AS
SELECT
  a.id,
  a.title,
  strip_html_tags(a.description) AS description_clean,
  a.due_at,
  a.lock_at,
  a.unlock_at,
  a.points_possible,
  a.grading_type,
  a.submission_types,
  a.context_id AS course_id,
  a.updated_at
FROM assignments a
WHERE a.workflow_state = 'published'
  AND a.context_type = 'Course';

-- All published pages
CREATE OR REPLACE VIEW ai_course_pages AS
SELECT
  wp.id,
  wp.title,
  wp.url,
  strip_html_tags(wp.body) AS body_clean,
  wp.context_id AS course_id,
  wp.updated_at
FROM wiki_pages wp
WHERE wp.workflow_state = 'active'
  AND wp.context_type = 'Course';

-- Module structure with items resolved
CREATE OR REPLACE VIEW ai_course_modules AS
SELECT
  cm.id AS module_id,
  cm.name AS module_name,
  cm.position,
  cm.prerequisites,
  cm.completion_requirements,
  ct.position AS item_position,
  ct.title AS item_title,
  ct.content_type,
  ct.content_id,
  ct.url AS external_url,
  ct.indent,
  cm.context_id AS course_id
FROM context_modules cm
LEFT JOIN content_tags ct
  ON ct.context_module_id = cm.id
  AND ct.workflow_state = 'active'
WHERE cm.workflow_state = 'active'
  AND cm.context_type = 'Course'
ORDER BY cm.position, ct.position;

-- Announcements (recent first)
CREATE OR REPLACE VIEW ai_course_announcements AS
SELECT
  dt.id,
  dt.title,
  strip_html_tags(dt.message) AS message_clean,
  dt.posted_at,
  dt.context_id AS course_id,
  dt.updated_at
FROM discussion_topics dt
WHERE dt.type = 'Announcement'
  AND dt.workflow_state = 'active'
  AND dt.context_type = 'Course'
ORDER BY dt.posted_at DESC;

-- Course syllabus
CREATE OR REPLACE VIEW ai_course_syllabus AS
SELECT
  c.id AS course_id,
  c.name,
  c.course_code,
  strip_html_tags(c.syllabus_body) AS syllabus_clean
FROM courses c
WHERE c.workflow_state = 'available';

-- Files list
CREATE OR REPLACE VIEW ai_course_files AS
SELECT
  a.id,
  a.display_name,
  a.filename,
  a.content_type,
  a.size,
  a.context_id AS course_id,
  a.updated_at
FROM attachments a
WHERE a.file_state = 'available'
  AND a.context_type = 'Course';

-- Unified content search (all content types in one view)
CREATE OR REPLACE VIEW ai_course_content AS
SELECT course_id, 'assignment' AS content_type, id AS content_id,
       title, description_clean AS content_clean, due_at AS relevant_date,
       points_possible, updated_at
FROM ai_course_assignments
UNION ALL
SELECT course_id, 'page', id, title, body_clean, NULL, NULL, updated_at
FROM ai_course_pages
UNION ALL
SELECT course_id, 'announcement', id, title, message_clean, posted_at, NULL, updated_at
FROM ai_course_announcements;

-- Course manifest (compact index for agent system prompt)
CREATE OR REPLACE VIEW ai_course_manifest AS
SELECT
  c.id AS course_id,
  c.name AS course_name,
  c.course_code,
  (SELECT count(*) FROM context_modules WHERE context_id = c.id AND workflow_state = 'active') AS module_count,
  (SELECT count(*) FROM assignments WHERE context_id = c.id AND workflow_state = 'published') AS assignment_count,
  (SELECT count(*) FROM wiki_pages wp WHERE wp.context_id = c.id AND wp.context_type = 'Course' AND wp.workflow_state = 'active') AS page_count,
  (SELECT count(*) FROM discussion_topics WHERE context_id = c.id AND type = 'Announcement' AND workflow_state = 'active') AS announcement_count,
  (SELECT count(*) FROM attachments WHERE context_id = c.id AND file_state = 'available') AS file_count
FROM courses c
WHERE c.workflow_state = 'available';
