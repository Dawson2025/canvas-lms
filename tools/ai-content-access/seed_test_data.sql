-- Canvas AI Content Access — Test Data
-- Seed data based on our actual CSE 290R course (407700)

-- Course
INSERT INTO courses (id, name, course_code, syllabus_body, workflow_state) VALUES
(407700, 'Applied AI for Software Engineering', 'CSE 290R',
 '<div style="margin:0;padding:0;font-family:Georgia,serif;font-size:17px;"><h1 style="font-size:2rem;">Applied AI for Software Engineering</h1><p style="margin:0 0 1.1em;">Credits: 2. Format: Two meetings per week. Duration: 14 weeks.</p><h2 style="font-size:1.4rem;">Late Policy</h2><p>Late work will only be accepted with prior consent from the instructor or teaching assistant.</p><h2>Grading</h2><p>Phase 1 portfolio: 35%. Phase 2 MVP: 40%. Participation: 15%. Reflections: 10%.</p><h2>Academic Honesty</h2><p>Students do their own work with AI tools as specified in the course policy.</p></div>',
 'available');

-- Wiki for course
INSERT INTO wikis (id, context_id, context_type) VALUES (1, 407700, 'Course');

-- Wiki Pages (instruction pages)
INSERT INTO wiki_pages (id, wiki_id, title, url, body, workflow_state) VALUES
(1, 1, 'Instruction 1.2: Agents', 'instruction-1-dot-2-agents',
 '<h1>Instruction 1.2: Agents</h1><h2>Definitions</h2><p><strong>Agents</strong>: AI systems that observe, reason, and act autonomously to achieve objectives.</p><p><strong>Markdown</strong>: Lightweight markup language for formatting text.</p>',
 'active'),
(2, 1, 'Instruction 2.1: Feature Planning', 'instruction-2-dot-1-feature-planning',
 '<h1>Instruction 2.1: Feature Planning</h1><h2>Definitions</h2><p><strong>Feature</strong>: A distinct, user-facing capability that adds value.</p><p><strong>Feature Scope</strong>: Boundaries of what a feature includes.</p><p><strong>FERPA</strong>: Federal law protecting student education records.</p>',
 'active');

-- Assignments
INSERT INTO assignments (id, context_id, title, description, due_at, points_possible, workflow_state) VALUES
(16835639, 407700, 'Prepare: 3.2 - Status',
 '<div style="font-family:Georgia;"><p>This is a <strong>graded survey</strong>: you receive credit for thoughtful completion.</p><p><strong>Unlimited attempts</strong> are allowed.</p></div>',
 '2026-05-07 10:15:00', 10, 'published'),
(16835669, 407700, 'Lab 3.2: Agent Driven Feature Implementation',
 '<div style="font-family:Georgia;font-size:17px;"><h1 style="font-size:2rem;">Lab 3.2: Agent Driven Feature Implementation</h1><p>You will begin implementing the Canvas feature you scoped and planned.</p><h2>Goal</h2><ol><li>Plans as source of truth</li><li>Implementation agent: agents/feature-implementation.md</li><li>Board workflow via MCP</li></ol><h2>Repository layout</h2><table><tr><th>Path</th><th>Purpose</th></tr><tr><td>agents/feature-implementation.md</td><td>Agent spec</td></tr><tr><td>agents/tasks/feature-1/implementation-evidence.md</td><td>Evidence pack</td></tr></table></div>',
 '2026-05-09 23:59:59', 30, 'published'),
(16835641, 407700, 'Prepare: 4.1 - Quality Assurance',
 '<div><p>Review definitions for QA, unit testing, TDD.</p><p><strong>Unlimited attempts.</strong> Highest score kept.</p></div>',
 '2026-05-12 10:15:00', 10, 'published'),
(16835671, 407700, 'Lab 4.1: Quality Assurance',
 '<div style="font-family:Georgia;"><h1>Lab 4.1: Quality Assurance</h1><p>Add a dedicated QA agent alongside your implementation workflow.</p><h2>Repository layout</h2><table><tr><th>Path</th><th>Purpose</th></tr><tr><td>agents/quality-assurance.md</td><td>QA agent spec</td></tr><tr><td>agents/tasks/feature-1/qa-lab-evidence.md</td><td>Test evidence</td></tr></table></div>',
 '2026-05-14 23:59:00', 30, 'published');

-- An unpublished assignment (should NOT appear in AI views — FERPA)
INSERT INTO assignments (id, context_id, title, description, due_at, points_possible, workflow_state) VALUES
(99999, 407700, 'SECRET DRAFT EXAM', '<p>This should never be visible to students.</p>', '2026-06-01 23:59:00', 100, 'unpublished');

-- Modules
INSERT INTO context_modules (id, context_id, name, position, prerequisites, workflow_state) VALUES
(4590003, 407700, 'Brownfield - Week 1', 1, '[]', 'active'),
(4590005, 407700, 'Brownfield - Week 2', 2, '[{"id":4590003,"type":"context_module","name":"Brownfield - Week 1"}]', 'active'),
(4590007, 407700, 'Brownfield - Week 3', 3, '[{"id":4590005,"type":"context_module","name":"Brownfield - Week 2"}]', 'active'),
(4590009, 407700, 'Brownfield - Week 4', 4, '[{"id":4590007,"type":"context_module","name":"Brownfield - Week 3"}]', 'active');

-- Content Tags (module items)
INSERT INTO content_tags (context_id, context_module_id, content_type, content_id, title, position, workflow_state) VALUES
(407700, 4590007, 'ContextModuleSubHeader', NULL, 'Day 5 - Memory', 1, 'active'),
(407700, 4590007, 'Assignment', 16835639, 'Prepare: 3.2 - Status', 2, 'active'),
(407700, 4590007, 'Assignment', 16835669, 'Lab 3.2: Agent Driven Feature Implementation', 3, 'active'),
(407700, 4590009, 'ContextModuleSubHeader', NULL, 'Day 7 - Quality Assurance', 1, 'active'),
(407700, 4590009, 'Assignment', 16835641, 'Prepare: 4.1 - Quality Assurance', 2, 'active'),
(407700, 4590009, 'Assignment', 16835671, 'Lab 4.1: Quality Assurance', 3, 'active');

-- Announcements
INSERT INTO discussion_topics (id, context_id, title, message, type, workflow_state, posted_at) VALUES
(1, 407700, 'Welcome to CSE 290R!',
 '<p style="font-family:Georgia;">Welcome to Applied AI for Software Engineering. Please review the syllabus and complete your tool setup before Day 1.</p>',
 'Announcement', 'active', '2026-04-20 09:00:00'),
(2, 407700, 'Lab 3.1 Submission Reminder',
 '<p>Remember to submit Lab 3.1 by Tuesday 11:59 PM. Include your memory-practice.md and AWS evidence.</p>',
 'Announcement', 'active', '2026-05-04 10:00:00');

-- Files
INSERT INTO attachments (id, context_id, display_name, filename, content_type, size, file_state) VALUES
(1, 407700, 'Course Overview Slides', 'course-overview.pdf', 'application/pdf', 2048000, 'available'),
(2, 407700, 'Canvas Architecture Diagram', 'canvas-arch.png', 'image/png', 512000, 'available');
