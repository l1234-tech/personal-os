# Локальная разработка

## Docker Compose
1. Установите Docker Desktop с Docker Compose.
2. Скопируйте .env.example в .env и замените локальные секреты.
3. Выполните `docker compose up --build`.
4. Web: http://localhost:5173; Swagger: http://localhost:8000/docs; health: http://localhost:8000/api/v1/health.

## Backend без Docker
Python 3.12 рекомендуется.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Команды: `pytest`, `ruff check .`, `mypy app`.

## Frontend без Docker

```powershell
cd apps/web
npm install
npm run dev
npm run lint
npm run typecheck
npm run build
```

Переменная VITE_API_BASE_URL задаёт API base URL; по умолчанию http://localhost:8000/api/v1.

## Правило изменений
1. Прочитайте docs/SPEC.md и соответствующий ADR.
2. Ветка — один небольшой домен/feature от актуальной main.
3. Укажите scope и acceptance criteria.
4. Добавьте unit и integration tests, особенно на permissions, concurrency и идемпотентность.
5. Запустите lint/typecheck/tests/build и прикрепите результаты к PR.
6. Не заявляйте об успешных проверках, которые не запускались.
7. Не коммитьте .env, пользователей, токены или личные данные.

Foundation endpoints не реализуют auth и доменные CRUD-функции. Не разворачивайте её в открытый production с персональными данными.
