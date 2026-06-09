# frozen_string_literal: true

#
# Copyright (C) 2026 - present Instructure, Inc.
#
# This file is part of Canvas.
#
# Canvas is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, version 3 of the License.
#

# Course AI Assistant: a one-button, course-agnostic AI assistant for a course.
# The page embeds the agent backend (grounded in the course's published content
# via the ai_course_* views) scoped to this course's id.
class CourseAiAssistantController < ApplicationController
  before_action :require_context
  before_action :check_feature_flag
  after_action :allow_local_agent_frame_src, only: :show

  def show
    return unless authorized_action(@context, @current_user, :read)

    set_active_tab "course_ai_assistant"
    add_crumb t("#crumbs.course_ai_assistant", "Course AI Assistant")
    @page_title = t("#page_title.course_ai_assistant", "Course AI Assistant")
    # The agent backend URL is configurable; defaults to the local dev service.
    @agent_base_url = ENV["COURSE_AI_AGENT_URL"].presence || "http://localhost:8742"
  end

  private

  def check_feature_flag
    unless @context&.feature_enabled?(:course_ai_assistant)
      render status: :not_found, template: "shared/errors/404_message"
    end
  end

  def allow_local_agent_frame_src
    csp = response.headers["Content-Security-Policy"]
    return if csp.blank?

    local_agent_sources = %w[http://localhost:* http://127.0.0.1:*]
    response.headers["Content-Security-Policy"] = if csp.match?(/frame-src\s+[^;]*/)
                                                    csp.sub(/frame-src\s+([^;]*)/) do
                                                      sources = Regexp.last_match(1).split
                                                      "frame-src #{(sources + local_agent_sources).uniq.join(" ")}"
                                                    end
                                                  else
                                                    "#{csp.chomp(";")}; frame-src 'self' #{local_agent_sources.join(" ")};"
                                                  end
  end
end
