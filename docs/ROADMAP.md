# Roadmap

## Stage 0 — Foundation (feat/foundation)
- [x] Зафиксировать MVP, архитектуру и логическую модель.
- [ ] Каркас Docker Compose, API, PWA и CI проходит проверки GitHub Actions.
- [ ] Проверить запуск на Windows/Docker Desktop.

## Stage 1 — Auth / backend security (feat/auth-security)
- [ ] SQLAlchemy models, Alembic migrations и PostgreSQL integration tests.
- [ ] User, invitation, safe session lifecycle.
- [ ] Ownership helpers и cross-user authorization tests.
- [ ] CORS, rate limiting, request IDs, structured logs.

## Stage 2 — Tasks and time (feat/tasks-time-tracking)
- [x] CRUD задач/категорий/сроков (базовый API и клиентские операции создания/изменения статуса).
- [x] Таймер с DB-инвариантом одной активной сессии на пользователя (start/pause/resume/stop).
- [x] Manual time entries: создание записей, история и суммарное фактическое время.
- [x] Корректировки существующих записей и plan-vs-actual (редактирование, связь с задачей, сравнение оценки и факта).
- [x] Dashboard подключён к API: реальные задачи, состояние таймера, фильтрация, ошибки и сетевой индикатор.
- [ ] Offline read-only cache и last-synced marker (отдельная доработка).

## Stage 3 — Calendar and planning (feat/calendar-planning)
- [ ] Google OAuth, selected calendars, incremental cursor, duplicate protection.
- [ ] Recurring-event, move/cancel и timezone cases.
- [ ] Explainable scheduler, conflicts/overload and plan preview.
- [ ] Calendar write only after explicit confirmation.

## Stage 4 — Tutoring (feat/tutoring)
- [ ] Students, lessons, topics/homework and progress notes.
- [ ] Reschedule/cancel/no-show and correction of actual lesson status.
- [ ] Accruals, partial payments, allocations and debt.
- [ ] Preparation time and effective hourly income.

## Stage 5 — Studies and projects (feat/studies-projects)
- [ ] Academic items/topics/resources.
- [ ] Project stages/milestones/results and time links.
- [ ] GitHub OAuth, repo selection and sync status.

## Stage 6 — Analytics and automation (feat/integrations-analytics)
- [ ] Tested formulas for daily/weekly outcome reports.
- [ ] Worker queue with retry/backoff and deduplication.
- [ ] Telegram account linking, preferences and notifications.

## Stage 7 — Production readiness
- [ ] Hosting/domain, HTTPS, monitoring and alerts.
- [ ] Encrypted daily backups and tested restore.
- [ ] Security review and integration/browser tests.
- [ ] Windows/iPhone PWA smoke tests.
- [ ] Personal finance tracking and exports after MVP.
