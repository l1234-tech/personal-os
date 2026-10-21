# Архитектура

## Решение
Модульный монолит: FastAPI backend, React PWA, PostgreSQL и отдельный worker для фоновых задач. Микросервисы/Kubernetes не нужны до появления подтверждённой нагрузки или самостоятельных циклов релизов.

## Стек
- Frontend: React, TypeScript, Vite, installable PWA.
- API: FastAPI, Pydantic, REST/OpenAPI.
- Persistence: PostgreSQL, SQLAlchemy 2.x, Alembic.
- Проверки: pytest, HTTP integration tests, frontend lint/typecheck/build, Playwright на UI-этапе.
- Runtime: Docker Compose; CI: GitHub Actions.
- Интеграции: адаптеры Google Calendar, GitHub и Telegram только на backend/worker.
- Logging: structured logs, request ID, health/readiness; не логировать credentials.

## Домены backend
auth, tasks, planning, time_tracking, tutoring, studies, projects, integrations, analytics, notifications, audit. Доменные операции не должны создавать циклические импорты; межмодульные workflows координируются application services.

## Поток данных
PWA → REST API → auth/ownership checks → application/domain services → repositories/SQLAlchemy → PostgreSQL. Интеграции и долгие вычисления выполняются worker-ом. OAuth credentials никогда не отдаются клиенту после callback.

## Инварианты
- timestamps timezone-aware, хранение преимущественно UTC; отображение в timezone пользователя.
- каждый запрос проверяет ownership/workspace membership.
- уникальность external IDs ограничена интеграцией и владельцем.
- не более одного активного таймера на пользователя.
- плановый блок не равен фактическому выполнению; факт урока не равен оплате.
- jobs и sync идемпотентны.
- внешние изменения требуют подтверждения пользователя.

## Deployment
Docker Compose — development only. Production требует HTTPS, сетевого ограничения БД, secret manager, миграционного процесса, encrypted backups, мониторинга и restore drills. Облачный провайдер выбирается отдельно до production deploy.
