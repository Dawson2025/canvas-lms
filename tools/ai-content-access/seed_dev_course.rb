# Idempotent dev seed: two real Canvas courses with content + a teacher & student,
# so the Course AI Assistant has real, course-scoped data to answer from.
# Run: docker compose exec -T web bundle exec rails runner tools/ai-content-access/seed_dev_course.rb
acct = Account.default

def upsert_user(acct, email, name)
  p = Pseudonym.active.by_unique_id(email).first
  return p.user if p
  u = User.create!(name: name, workflow_state: "registered")
  u.pseudonyms.create!(account: acct, unique_id: email, password: "canvasdev123", password_confirmation: "canvasdev123")
  cc = u.communication_channels.create!(path: email, path_type: "email")
  cc.confirm
  u
end

teacher = Pseudonym.active.by_unique_id("admin@canvas.docker").first&.user || upsert_user(acct, "teacher@canvas.docker", "Demo Teacher")
student = upsert_user(acct, "student@canvas.docker", "Demo Student")

def make_course(acct, teacher, student, code, name, syllabus, assignments)
  c = acct.courses.where(course_code: code).first || acct.courses.create!(course_code: code, name: name)
  c.offer! unless c.available?
  c.update!(syllabus_body: syllabus)
  c.enroll_teacher(teacher, enrollment_state: "active") unless c.teachers.include?(teacher)
  c.enroll_student(student, enrollment_state: "active") unless c.students.include?(student)
  assignments.each do |title, days, pts, desc|
    next if c.assignments.where(title: title).exists?
    a = c.assignments.new(title: title, description: desc, points_possible: pts, submission_types: "online_text_entry")
    a.due_at = days.days.from_now if days
    a.workflow_state = "published"
    a.save!
  end
  c
end

c1 = make_course(acct, teacher, student, "CSE 290R", "Special Topics — Applied AI",
  "<h1>CSE 290R Syllabus</h1><p><strong>Late policy:</strong> Assignments may be submitted up to 3 days late with a 10% per-day penalty. After 3 days, no credit is given.</p><p>Class meets TR 10:15–11:15 in STC 375. Office hours by appointment.</p><p><strong>Grading:</strong> Labs 60%, Prepares 20%, Participation 20%.</p>",
  [["Lab 4.2 — Course AI Platform", 3, 30, "<p>Build and demo the one-button course AI assistant that works for any course.</p>"],
   ["Prepare 4.1 — Agent Memory", -2, 10, "<p>Read the assigned chapters on short-term vs long-term agent memory.</p>"],
   ["Lab 4.1 — Quality Assurance", 6, 30, "<p>Write unit tests (AAA pattern) and a QA report for your feature.</p>"]])

c2 = make_course(acct, teacher, student, "AI Society", "AI Society",
  "<h1>AI Society</h1><p>Student club for applied AI. <strong>Attendance policy:</strong> members who miss 3 consecutive meetings are moved to inactive.</p><p>Meetings every other Thursday at 7pm.</p>",
  [["Kickoff RSVP", 2, 5, "<p>RSVP for the semester kickoff meeting.</p>"],
   ["Project Pitch", 9, 20, "<p>Pitch a project for the club showcase.</p>"]])

puts "SEED_OK teacher=#{teacher.id} student=#{student.id} cse290r=#{c1.id} aisociety=#{c2.id}"
