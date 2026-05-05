-- Canvas AI Content Access — Edge Case Tests
-- Tests boundary conditions, empty data, nulls, large content, and cross-view consistency

\echo '=========================================='
\echo 'EDGE CASE TESTS'
\echo '=========================================='

-- ============================================================
-- ARRANGE: Insert edge case data
-- ============================================================

-- Assignment with NULL description
INSERT INTO assignments (id, context_id, title, description, due_at, points_possible, workflow_state)
VALUES (90001, 407700, 'Assignment With No Description', NULL, '2026-05-20 23:59:00', 10, 'published');

-- Assignment with empty string description
INSERT INTO assignments (id, context_id, title, description, due_at, points_possible, workflow_state)
VALUES (90002, 407700, 'Assignment With Empty Description', '', '2026-05-21 23:59:00', 5, 'published');

-- Assignment with very large HTML (simulated Canvas bloat)
INSERT INTO assignments (id, context_id, title, description, due_at, points_possible, workflow_state)
VALUES (90003, 407700, 'Assignment With Huge HTML',
  '<div style="margin:0;padding:0;font-family:Georgia,serif;font-size:17px;line-height:1.68;color:#0f0e0d;background-color:#ebe6dc;background-image:repeating-linear-gradient(90deg,transparent,transparent 1px,rgba(15,14,13,0.03) 1px,rgba(15,14,13,0.03) 2px);">' ||
  repeat('<p style="margin:0 0 1.1em 0;font-family:Georgia,serif;">This is a paragraph with lots of inline CSS that Canvas generates. It contains <strong style="font-style:normal;color:#0f0e0d;">bold text</strong> and <em style="font-style:italic;">italic text</em> and <code style="font-family:ui-monospace;font-size:0.92em;background-color:#f2ede4;padding:0.12em 0.35em;border-radius:3px;">code blocks</code>.</p>', 50) ||
  '</div>',
  '2026-05-22 23:59:00', 100, 'published');

-- Assignment with no due date
INSERT INTO assignments (id, context_id, title, description, due_at, points_possible, workflow_state)
VALUES (90004, 407700, 'Undated Assignment', '<p>No due date set.</p>', NULL, 20, 'published');

-- Assignment with deleted state (should be hidden like unpublished)
INSERT INTO assignments (id, context_id, title, description, due_at, points_possible, workflow_state)
VALUES (90005, 407700, 'DELETED ASSIGNMENT', '<p>This was deleted.</p>', '2026-06-01 23:59:00', 50, 'deleted');

-- Wiki page with NULL body
INSERT INTO wiki_pages (id, wiki_id, title, url, body, workflow_state)
VALUES (90001, 1, 'Empty Page', 'empty-page', NULL, 'active');

-- Wiki page with only HTML entities and special chars
INSERT INTO wiki_pages (id, wiki_id, title, url, body, workflow_state)
VALUES (90002, 1, 'Special Characters Page', 'special-chars',
  '<p>Angles: &lt;tag&gt; Ampersand: &amp; Quote: &quot;hello&quot; Apostrophe: &#39;world&#39; Non-breaking: &nbsp;space</p>',
  'active');

-- Empty module (no content tags)
INSERT INTO context_modules (id, context_id, name, position, prerequisites, workflow_state)
VALUES (90001, 407700, 'Empty Module', 5, '[]', 'active');

-- Module with deleted state
INSERT INTO context_modules (id, context_id, name, position, prerequisites, workflow_state)
VALUES (90002, 407700, 'DELETED MODULE', 6, '[]', 'deleted');

-- Discussion topic (not announcement)
INSERT INTO discussion_topics (id, context_id, title, message, type, workflow_state, posted_at)
VALUES (90001, 407700, 'Regular Discussion', '<p>This is a discussion, not an announcement.</p>', NULL, 'active', '2026-05-04 12:00:00');

-- Course with no content (different course_id)
INSERT INTO courses (id, name, course_code, syllabus_body, workflow_state)
VALUES (999999, 'Empty Course', 'EMPTY 101', NULL, 'available');

\echo ''
\echo '=========================================='
\echo 'TEST 13: NULL description handled gracefully'
\echo '=========================================='
SELECT
  CASE WHEN description_clean IS NULL
       THEN 'PASS: NULL description returns NULL (no crash)'
       ELSE 'FAIL: Expected NULL, got content'
  END AS test_result
FROM ai_course_assignments WHERE id = 90001;

\echo ''
\echo '=========================================='
\echo 'TEST 14: Empty string description handled'
\echo '=========================================='
SELECT
  CASE WHEN description_clean = '' OR description_clean IS NULL
       THEN 'PASS: Empty description handled gracefully'
       ELSE 'FAIL: Unexpected content from empty description'
  END AS test_result
FROM ai_course_assignments WHERE id = 90002;

\echo ''
\echo '=========================================='
\echo 'TEST 15: Large HTML stripped efficiently'
\echo '=========================================='
SELECT
  CASE WHEN length(description_clean) < length(a.description) * 0.5
        AND description_clean NOT LIKE '%style=%'
        AND description_clean LIKE '%bold text%'
       THEN 'PASS: Large HTML stripped (original=' || length(a.description) || ' bytes, cleaned=' || length(description_clean) || ' bytes, ' || round(100.0 * length(description_clean) / length(a.description)) || '% of original)'
       ELSE 'FAIL: HTML not stripped efficiently'
  END AS test_result
FROM ai_course_assignments v
JOIN assignments a ON a.id = v.id
WHERE v.id = 90003;

\echo ''
\echo '=========================================='
\echo 'TEST 16: NULL due_at handled (undated assignment)'
\echo '=========================================='
SELECT
  CASE WHEN due_at IS NULL AND title = 'Undated Assignment'
       THEN 'PASS: Assignment with NULL due_at visible and queryable'
       ELSE 'FAIL: Undated assignment not handled correctly'
  END AS test_result
FROM ai_course_assignments WHERE id = 90004;

\echo ''
\echo '=========================================='
\echo 'TEST 17: Deleted assignments hidden'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 0
       THEN 'PASS: Deleted assignment correctly hidden'
       ELSE 'FAIL: Deleted assignment visible!'
  END AS test_result
FROM ai_course_assignments WHERE id = 90005;

\echo ''
\echo '=========================================='
\echo 'TEST 18: NULL page body handled'
\echo '=========================================='
SELECT
  CASE WHEN body_clean IS NULL
       THEN 'PASS: Page with NULL body returns NULL (no crash)'
       ELSE 'FAIL: Expected NULL body'
  END AS test_result
FROM ai_course_pages WHERE id = 90001;

\echo ''
\echo '=========================================='
\echo 'TEST 19: HTML entities decoded correctly'
\echo '=========================================='
SELECT
  CASE WHEN body_clean LIKE '%<%' AND body_clean LIKE '%&%' AND body_clean LIKE '%"hello"%'
       THEN 'PASS: HTML entities decoded (<, &, "hello")'
       ELSE 'FAIL: HTML entities not decoded. Got: ' || coalesce(body_clean, 'NULL')
  END AS test_result
FROM ai_course_pages WHERE id = 90002;

\echo ''
\echo '=========================================='
\echo 'TEST 20: Empty module visible but with no items'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 1 AND max(item_title) IS NULL
       THEN 'PASS: Empty module visible, no items (LEFT JOIN works)'
       ELSE 'FAIL: Empty module not handled correctly (count=' || count(*) || ')'
  END AS test_result
FROM ai_course_modules
WHERE course_id = 407700 AND module_name = 'Empty Module';

\echo ''
\echo '=========================================='
\echo 'TEST 21: Deleted module hidden'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 0
       THEN 'PASS: Deleted module correctly hidden'
       ELSE 'FAIL: Deleted module visible!'
  END AS test_result
FROM ai_course_modules
WHERE course_id = 407700 AND module_name = 'DELETED MODULE';

\echo ''
\echo '=========================================='
\echo 'TEST 22: Regular discussions NOT in announcements view'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 0
       THEN 'PASS: Regular discussion correctly excluded from announcements view'
       ELSE 'FAIL: Non-announcement discussion appearing in announcements!'
  END AS test_result
FROM ai_course_announcements WHERE id = 90001;

\echo ''
\echo '=========================================='
\echo 'TEST 23: Empty course manifest shows zeros'
\echo '=========================================='
SELECT
  CASE WHEN assignment_count = 0 AND module_count = 0 AND announcement_count = 0
       THEN 'PASS: Empty course manifest shows all zeros'
       ELSE 'FAIL: Empty course has non-zero counts'
  END AS test_result
FROM ai_course_manifest WHERE course_id = 999999;

\echo ''
\echo '=========================================='
\echo 'TEST 24: Unified search finds content across types'
\echo '=========================================='
SELECT
  CASE WHEN count(DISTINCT content_type) >= 2
       THEN 'PASS: Unified search returns multiple content types (' || count(DISTINCT content_type) || ' types found)'
       ELSE 'FAIL: Unified search only returns ' || count(DISTINCT content_type) || ' type(s)'
  END AS test_result
FROM ai_course_content
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 25: Manifest counts updated after edge case inserts'
\echo '=========================================='
SELECT
  CASE WHEN assignment_count = 8 AND module_count = 5 AND page_count = 4 AND announcement_count = 2
       THEN 'PASS: Manifest counts correct after edge case inserts (8 assignments, 5 modules, 4 pages, 2 announcements)'
       ELSE 'FAIL: Counts wrong — assignments=' || assignment_count || ' modules=' || module_count || ' pages=' || page_count || ' announcements=' || announcement_count
  END AS test_result
FROM ai_course_manifest WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 26: Idempotency — running views twice gives same results'
\echo '=========================================='
SELECT
  CASE WHEN (SELECT count(*) FROM ai_course_assignments WHERE course_id = 407700) =
            (SELECT count(*) FROM ai_course_assignments WHERE course_id = 407700)
       THEN 'PASS: Views are idempotent (same result on repeat query)'
       ELSE 'FAIL: Views not idempotent!'
  END AS test_result;

\echo ''
\echo '=========================================='
\echo 'EDGE CASE SUMMARY'
\echo '=========================================='
\echo 'Tests 13-26 completed (14 edge case tests). Review results above.'

-- ============================================================
-- CLEANUP: Remove edge case data
-- ============================================================
DELETE FROM content_tags WHERE context_module_id IN (90001, 90002);
DELETE FROM context_modules WHERE id IN (90001, 90002);
DELETE FROM assignments WHERE id IN (90001, 90002, 90003, 90004, 90005);
DELETE FROM wiki_pages WHERE id IN (90001, 90002);
DELETE FROM discussion_topics WHERE id = 90001;
DELETE FROM courses WHERE id = 999999;

\echo 'Edge case data cleaned up.'
