-- Canvas AI Content Access — Second course seed: AI Society (415990)
-- ILLUSTRATIVE content for the course-agnostic demo. The real BYUI course 415990
-- ("AI Society", owned by Dawson) is currently empty; this is placeholder content
-- so the "enable assistant for ANY course" flow is demonstrable. Replace with real
-- content when wiring the live course.

INSERT INTO courses (id, name, course_code, syllabus_body, workflow_state) VALUES
(415990, 'AI Society', 'AI Society',
 '<div style="font-family:Georgia,serif"><h1>AI Society</h1>'
 '<p>The AI Society is a <strong>student-led club</strong> for learning, building, '
 'and sharing projects with artificial intelligence. Everyone is welcome, from '
 'curious beginners to experienced builders.</p>'
 '<h2>How it works</h2>'
 '<p>Members progress through <strong>levels</strong>, starting at Level 1 (Novice). '
 'Each level unlocks new project tracks, workshops, and leadership opportunities.</p>'
 '<h2>Meetings</h2>'
 '<p>We meet <strong>weekly</strong> and coordinate between meetings on our '
 '<strong>Discord community</strong>.</p>'
 '<h2>Getting involved</h2>'
 '<p>Join the Discord, introduce yourself, and pick a starter project. No experience '
 'required.</p></div>',
 'available')
ON CONFLICT (id) DO NOTHING;

-- Wiki for AI Society (id 2; 290R uses id 1)
INSERT INTO wikis (id, context_id, context_type) VALUES (2, 415990, 'Course')
ON CONFLICT (id) DO NOTHING;

-- Pages
INSERT INTO wiki_pages (id, wiki_id, title, url, body, workflow_state) VALUES
(101, 2, 'About the AI Society', 'about',
 '<h1>About the AI Society</h1><p>We are a community of students exploring '
 '<strong>artificial intelligence</strong> through hands-on projects, talks, and '
 'collaboration. Our goal is to make AI approachable and to help members build real '
 'things they are proud of.</p>', 'active'),
(102, 2, 'Levels and Progression', 'levels',
 '<h1>Levels and Progression</h1><p>Membership is organized into levels:</p>'
 '<ul><li><strong>Level 1 - Novice</strong>: orientation, join the Discord, finish a '
 'starter project.</li><li><strong>Level 2 - Builder</strong>: ship a small AI app or '
 'notebook and present it.</li><li><strong>Level 3 - Contributor</strong>: lead a '
 'workshop or mentor newer members.</li></ul>', 'active'),
(103, 2, 'How to Get Involved', 'get-involved',
 '<h1>How to Get Involved</h1><ol><li>Join the <strong>Discord community</strong>.</li>'
 '<li>Come to a <strong>weekly meeting</strong>.</li><li>Pick a starter project from the '
 'Level 1 track.</li></ol><p>Questions? Ask in Discord - someone is always around.</p>',
 'active')
ON CONFLICT (id) DO NOTHING;

-- Module: the real course already has "Level 1: Novice" (id 4647581)
INSERT INTO context_modules (id, context_id, name, position, prerequisites, workflow_state) VALUES
(4647581, 415990, 'Level 1: Novice', 1, '[]', 'active')
ON CONFLICT (id) DO NOTHING;

-- Module items (pages)
INSERT INTO content_tags (context_id, context_module_id, content_type, content_id, title, position, workflow_state) VALUES
(415990, 4647581, 'WikiPage', 101, 'About the AI Society', 1, 'active'),
(415990, 4647581, 'WikiPage', 102, 'Levels and Progression', 2, 'active'),
(415990, 4647581, 'WikiPage', 103, 'How to Get Involved', 3, 'active');

-- Announcement
INSERT INTO discussion_topics (id, context_id, title, message, type, workflow_state, posted_at) VALUES
(101, 415990, 'Welcome to the AI Society!',
 '<p>Welcome! Join our <strong>Discord</strong>, say hi, and grab a Level 1 starter '
 'project. We meet weekly - hope to see you there.</p>',
 'Announcement', 'active', '2026-06-01 09:00:00')
ON CONFLICT (id) DO NOTHING;
