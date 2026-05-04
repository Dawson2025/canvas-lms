-- Canvas AI Content Access — Test Schema
-- Minimal reproduction of Canvas tables needed for AI views
-- This mirrors the actual Canvas schema for the relevant tables

-- Courses
CREATE TABLE IF NOT EXISTS courses (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  course_code TEXT,
  syllabus_body TEXT,  -- HTML content
  workflow_state TEXT DEFAULT 'available',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Wikis (each course has one wiki)
CREATE TABLE IF NOT EXISTS wikis (
  id BIGSERIAL PRIMARY KEY,
  context_id BIGINT,
  context_type TEXT DEFAULT 'Course',
  created_at TIMESTAMP DEFAULT NOW()
);

-- Wiki Pages
CREATE TABLE IF NOT EXISTS wiki_pages (
  id BIGSERIAL PRIMARY KEY,
  wiki_id BIGINT REFERENCES wikis(id),
  title TEXT NOT NULL,
  url TEXT,  -- slug
  body TEXT,  -- HTML content
  workflow_state TEXT DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Assignments
CREATE TABLE IF NOT EXISTS assignments (
  id BIGSERIAL PRIMARY KEY,
  context_id BIGINT,
  context_type TEXT DEFAULT 'Course',
  title TEXT NOT NULL,
  description TEXT,  -- HTML content
  due_at TIMESTAMP,
  lock_at TIMESTAMP,
  unlock_at TIMESTAMP,
  points_possible FLOAT,
  grading_type TEXT DEFAULT 'points',
  submission_types TEXT DEFAULT 'online_text_entry',
  workflow_state TEXT DEFAULT 'published',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Discussion Topics (also used for Announcements via STI)
CREATE TABLE IF NOT EXISTS discussion_topics (
  id BIGSERIAL PRIMARY KEY,
  context_id BIGINT,
  context_type TEXT DEFAULT 'Course',
  title TEXT,
  message TEXT,  -- HTML content
  type TEXT,  -- NULL for discussions, 'Announcement' for announcements
  workflow_state TEXT DEFAULT 'active',
  posted_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Context Modules
CREATE TABLE IF NOT EXISTS context_modules (
  id BIGSERIAL PRIMARY KEY,
  context_id BIGINT,
  context_type TEXT DEFAULT 'Course',
  name TEXT NOT NULL,
  position INTEGER,
  prerequisites TEXT,  -- serialized JSON array
  completion_requirements TEXT,  -- serialized JSON
  workflow_state TEXT DEFAULT 'active',
  unlock_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Content Tags (polymorphic module items)
CREATE TABLE IF NOT EXISTS content_tags (
  id BIGSERIAL PRIMARY KEY,
  context_id BIGINT,
  context_type TEXT DEFAULT 'Course',
  context_module_id BIGINT REFERENCES context_modules(id),
  content_id BIGINT,
  content_type TEXT,  -- 'Assignment', 'WikiPage', 'DiscussionTopic', etc.
  title TEXT,
  url TEXT,  -- for ExternalUrl type
  position INTEGER,
  indent INTEGER DEFAULT 0,
  workflow_state TEXT DEFAULT 'active',
  created_at TIMESTAMP DEFAULT NOW()
);

-- Attachments (files)
CREATE TABLE IF NOT EXISTS attachments (
  id BIGSERIAL PRIMARY KEY,
  context_id BIGINT,
  context_type TEXT DEFAULT 'Course',
  filename TEXT,
  display_name TEXT,
  content_type TEXT,
  size BIGINT,
  file_state TEXT DEFAULT 'available',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
