# Локальный запуск и проверка Personal OS

## Что уже можно проверить

Текущий MVP позволяет войти в аккаунт, создавать и отмечать задачи, запускать/приостанавливать/завершать фокус-таймер, добавлять и редактировать записи фактического времени и смотреть аналитику. Календарь, репетиторство, учёба/проекты и финансовый модуль пока не реализованы полностью.

## Самый простой способ: Docker Desktop

Требуются Docker Desktop с Compose и Git.

1. Склонируй репозиторий и перейди в него:

   ```powershell
   git clone https://github.com/l1234-tech/personal-os.git
   cd personal-os
   ```

2. Переключись на ветку с текущим MVP (пока изменения идут через PR):

   ```powershell
   git fetch origin
   git switch feat/time-analytics
   git pull
   ```

3. Создай локальный файл окружения:

   ```powershell
   Copy-Item .env.example .env
   ```

   Открой `.env` и замени `POSTGRES_PASSWORD` и `DATABASE_URL` на одинаковый локальный пароль, а `SECRET_KEY` — случайной строкой не короче 32 символов. Для локальной разработки оставь `COOKIE_SECURE=false`. Задай непустой `BOOTSTRAP_INVITATION_SECRET`, например длинную случайную строку. Файл `.env` не коммить.

4. Запусти приложение из корня репозитория:

   ```powershell
   docker compose up --build
   ```

   Первый запуск может занять несколько минут. Не закрывай терминал: в нём будут логи контейнеров.

5. Открой адреса:

   - Приложение: http://localhost:5173
   - API / Swagger: http://localhost:8000/docs
   - Проверка backend: http://localhost:8000/api/v1/health

6. Создай одноразовое приглашение для своего email через Swagger:

   - Найди `POST /api/v1/auth/invitations` и нажми **Try it out**.
   - В поле `x-bootstrap-secret` укажи значение `BOOTSTRAP_INVITATION_SECRET` из локального `.env`.
   - В теле запроса укажи свой email и срок действия, например `{"email":"you@example.com","expires_in_hours":72}`.
   - Нажми **Execute** и скопируй поле `token` из ответа. Это секрет приглашения — не публикуй его.
   - В приложении открой регистрацию и введи тот же email, пароль длиной не менее 12 символов и полученный invitation token.
   - После регистрации войди в приложение.

7. Для первой проверки создай тестовую задачу, запусти таймер, останови его, открой **Фокус и время**, добавь ручную запись и проверь страницу **Аналитика**. Проверь, что задача и записи остаются после перезапуска страницы.

Чтобы остановить приложение, нажми `Ctrl+C`. Контейнеры можно остановить командой `docker compose down`; данные Postgres сохраняются в Docker volume. Для полного удаления локальной базы используй `docker compose down -v` — это необратимо удалит локальные данные.

## Разработка без Docker

### Frontend

Требуется Node.js, совместимый с текущим Vite.

```powershell
cd apps/web
npm install
npm run dev
npm run lint
npm run typecheck
npm run build
```

Frontend по умолчанию обращается к `http://localhost:8000/api/v1`; backend и PostgreSQL всё равно должны быть запущены.

### Backend

Рекомендуется Python 3.12. Удобнее всего запустить PostgreSQL отдельно и задать `DATABASE_URL` и остальные настройки из `backend/.env.example`.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Проверки backend: `pytest`, `ruff check .`, `mypy app`.

## Перед сообщением об ошибке

Приложи текст ошибки, шаги воспроизведения и относящиеся к ним логи. Не прикладывай пароль, cookie, invitation token, секреты из `.env` или личные данные. Если интерфейс не открывается, сначала проверь, что Docker Desktop запущен и контейнеры `db`, `api` и `web` находятся в рабочем состоянии.

## Правило изменений

1. Прочитай `docs/SPEC.md` и соответствующий ADR.
2. Делай небольшую feature-ветку от актуальной интеграционной ветки.
3. Укажи scope и acceptance criteria.
4. Добавь unit- и integration-тесты, особенно для permissions, concurrency и идемпотентности.
5. Запусти lint/typecheck/tests/build и приложи результаты к PR.
6. Не заявляй об успешных проверках, которые не запускались.
7. Не коммить `.env`, пользователей, токены или личные данные.

> Это развиваемый MVP, а не production-релиз. Пока не разворачивай его публично и не используй для хранения чувствительных личных данных.
