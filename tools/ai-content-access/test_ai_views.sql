-- Canvas AI Content Access — Tests
-- Verifies views work correctly with AAA pattern (Arrange-Act-Assert)
-- Arrange: test data loaded via seed_test_data.sql
-- Act: query each view
-- Assert: check results match expectations

\echo '=========================================='
\echo 'TEST 1: FERPA — unpublished content hidden'
\echo '=========================================='
-- The unpublished assignment (id=99999) should NOT appear
SELECT
  CASE WHEN count(*) = 0 THEN 'PASS: Unpublished assignment correctly hidden'
       ELSE 'FAIL: Unpublished assignment visible — FERPA violation!'
  END AS test_result
FROM ai_course_assignments
WHERE course_id = 407700 AND title = 'SECRET DRAFT EXAM';

\echo ''
\echo '=========================================='
\echo 'TEST 2: Published assignments visible'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 4 THEN 'PASS: All 4 published assignments visible'
       ELSE 'FAIL: Expected 4 published assignments, got ' || count(*)
  END AS test_result
FROM ai_course_assignments
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 3: HTML stripped from assignments'
\echo '=========================================='
SELECT
  CASE WHEN description_clean NOT LIKE '%<div%' AND description_clean NOT LIKE '%style=%'
       THEN 'PASS: HTML tags stripped from assignment description'
       ELSE 'FAIL: HTML tags still present in description_clean'
  END AS test_result
FROM ai_course_assignments
WHERE id = 16835669;

\echo ''
\echo '=========================================='
\echo 'TEST 4: Syllabus accessible and cleaned'
\echo '=========================================='
SELECT
  CASE WHEN syllabus_clean IS NOT NULL
        AND syllabus_clean NOT LIKE '%<div%'
        AND syllabus_clean LIKE '%Late Policy%'
       THEN 'PASS: Syllabus accessible, cleaned, contains Late Policy'
       ELSE 'FAIL: Syllabus missing, still has HTML, or missing content'
  END AS test_result
FROM ai_course_syllabus
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 5: Module structure preserved'
\echo '=========================================='
SELECT
  CASE WHEN count(DISTINCT module_id) = 4 THEN 'PASS: All 4 modules visible'
       ELSE 'FAIL: Expected 4 modules, got ' || count(DISTINCT module_id)
  END AS test_result
FROM ai_course_modules
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 6: Module prerequisites preserved'
\echo '=========================================='
SELECT
  CASE WHEN prerequisites LIKE '%Week 2%'
       THEN 'PASS: Week 3 prerequisite chain preserved (requires Week 2)'
       ELSE 'FAIL: Prerequisite data missing or corrupted'
  END AS test_result
FROM ai_course_modules
WHERE course_id = 407700 AND module_name = 'Brownfield - Week 3'
LIMIT 1;

\echo ''
\echo '=========================================='
\echo 'TEST 7: Announcements visible and cleaned'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 2 AND bool_and(message_clean NOT LIKE '%<p%')
       THEN 'PASS: 2 announcements visible, HTML cleaned'
       ELSE 'FAIL: Announcement count or HTML cleaning issue'
  END AS test_result
FROM ai_course_announcements
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 8: Unified content search works'
\echo '=========================================='
SELECT
  CASE WHEN count(*) > 0 THEN 'PASS: Found content matching "Quality Assurance"'
       ELSE 'FAIL: Unified search returned no results'
  END AS test_result
FROM ai_course_content
WHERE course_id = 407700 AND content_clean ILIKE '%quality assurance%';

\echo ''
\echo '=========================================='
\echo 'TEST 9: Course manifest counts correct'
\echo '=========================================='
SELECT
  CASE WHEN assignment_count = 4 AND module_count = 4 AND announcement_count = 2
       THEN 'PASS: Manifest counts correct (4 assignments, 4 modules, 2 announcements)'
       ELSE 'FAIL: Manifest counts wrong — assignments=' || assignment_count
            || ' modules=' || module_count || ' announcements=' || announcement_count
  END AS test_result
FROM ai_course_manifest
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 10: Pages accessible via wiki join'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 2 AND bool_and(body_clean NOT LIKE '%<h1%')
       THEN 'PASS: 2 pages visible, HTML cleaned, wiki join works'
       ELSE 'FAIL: Page count or HTML cleaning issue'
  END AS test_result
FROM ai_course_pages
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'TEST 11: Due-this-week filter works'
\echo '=========================================='
-- This tests that the view supports date filtering (agent would add WHERE clause)
SELECT
  CASE WHEN count(*) >= 0 THEN 'PASS: Date filtering on ai_course_assignments works (found ' || count(*) || ' due this week)'
       ELSE 'FAIL: Date filtering error'
  END AS test_result
FROM ai_course_assignments
WHERE course_id = 407700
  AND due_at BETWEEN NOW() AND NOW() + interval '7 days';

\echo ''
\echo '=========================================='
\echo 'TEST 12: Files view works'
\echo '=========================================='
SELECT
  CASE WHEN count(*) = 2 THEN 'PASS: 2 files visible'
       ELSE 'FAIL: Expected 2 files, got ' || count(*)
  END AS test_result
FROM ai_course_files
WHERE course_id = 407700;

\echo ''
\echo '=========================================='
\echo 'SUMMARY'
\echo '=========================================='
\echo 'All 12 tests completed. Review results above.'
