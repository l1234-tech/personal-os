# Логическая модель данных

Это логическая схема; физические таблицы создаются небольшими миграциями при реализации домена.

## Accounts and integrations
- users(id, email, password_hash, timezone, is_active, created_at)
- workspaces(id, name, owner_id, created_at); workspace_members(workspace_id, user_id, role, joined_at)
- invitations(id, workspace_id, email, token_hash, expires_at, used_at)
- integrations(id, user_id, provider, external_account_id, status, scopes)
- integration_credentials(integration_id, encrypted_access_token, encrypted_refresh_token, expires_at)
- sync_cursors(integration_id, resource_type, cursor, last_synced_at)

## Tasks / plan / time
- calendar_events(id, user_id, source, external_id, title, start_at, end_at, status)
- tasks(id, user_id, workspace_id, title, description, status, priority, due_at, estimated_minutes)
- task_dependencies(task_id, depends_on_task_id)
- task_blocks(id, user_id, task_id, start_at, end_at, status, calendar_event_id)
- time_entries(id, user_id, task_id, project_id, student_id, category, started_at, ended_at, source)
- timer_sessions(id, user_id, time_entry_id, started_at, stopped_at, status)
- daily_reviews(id, user_id, review_date, summary, completed_at)
- notifications(id, user_id, channel, type, payload, deduplication_key, scheduled_at, sent_at, status)

## Tutoring
- students(id, user_id, name, subject, notes, status)
- lesson_templates(id, student_id, weekday, start_time, duration_minutes, price, timezone)
- lessons(id, user_id, student_id, calendar_event_id, scheduled_start, scheduled_end, actual_start, actual_end, status, price)
- lesson_topics(id, lesson_id, topic, notes); homework(id, student_id, lesson_id, title, due_at, status, result_notes)
- student_progress(id, student_id, topic, mastery_status, updated_at)
- payments(id, user_id, student_id, amount, status, paid_at, method) and payment allocations to lessons for partial/package payments.

## Studies / projects
- subjects(id, user_id, name, semester); study_topics(id, subject_id, name, status, mastery_status)
- academic_items(id, subject_id, title, type, due_at, status, result)
- resources(id, user_id, title, url, resource_type, related_entity_type, related_entity_id)
- projects(id, user_id, name, description, project_type, status, goal)
- project_stages(id, project_id, name, position, status, started_at, completed_at)
- project_repositories(id, project_id, provider, external_repo_id, repo_url, last_synced_at)
- project_milestones(id, project_id, title, due_at, status, result)
- task_results(id, user_id, task_id, result_type, description, resource_url, completed_at)

## Operations
audit_log, background_jobs, daily_summaries, weekly_reports, user_preferences, outbox_events.

## Constraints
User-owned rows have user_id or a verified workspace path. Add FKs, indexes on (user_id, date/status) and unique constraints for external IDs. Store timezone-aware timestamps. Store OAuth tokens encrypted. Logs must not contain tokens, passwords, student notes or private payloads. DB migrations need tests for constraints and isolation.
