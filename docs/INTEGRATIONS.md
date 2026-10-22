# Настройка интеграций

Все секреты задаются через локальный `.env` или секрет-хранилище хостинга. Не добавляйте реальные токены и OAuth secrets в Git.

## Google Calendar

1. В Google Cloud создайте OAuth 2.0 Client ID типа **Web application**.
2. Добавьте authorized redirect URI: `http://localhost:8000/api/v1/integrations/google/callback` для локальной разработки.
3. Заполните `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`.
4. Сгенерируйте ключ шифрования токенов командой:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
5. Поместите результат в `TOKEN_ENCRYPTION_KEY`. При смене ключа старые зашифрованные токены потребуется подключить заново.
6. Запустите приложение, войдите, откройте «Планировщик» и подключите Google. Выберите календари и нажмите синхронизацию.

Существующие события читаются из Google Calendar. Приложение не должно автоматически редактировать их; публикация новых блоков задач требует отдельного подтверждения.

## GitHub

1. Создайте GitHub OAuth App.
2. Укажите Homepage URL: `http://localhost:5173`.
3. Укажите callback URL: `http://localhost:8000/api/v1/integrations/github/callback`.
4. Заполните `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI` и тот же `TOKEN_ENCRYPTION_KEY`.
5. В Personal OS откройте «ML и проекты» и подключите GitHub. Выберите проект и привяжите к нему публичный репозиторий.

Текущая интеграция использует ограниченный read-only сценарий для публичных репозиториев. Частные репозитории не поддерживаются этим потоком; коммиты и PR — сигналы активности, а не самостоятельная мера продуктивности.

## Telegram

1. Через BotFather создайте бота и получите токен.
2. Заполните `TELEGRAM_BOT_TOKEN` и `TELEGRAM_BOT_USERNAME` (без символа `@`).
3. Сгенерируйте случайный секрет для webhook и задайте `TELEGRAM_WEBHOOK_SECRET`.
4. Разверните API по HTTPS. Telegram webhook требует публичный HTTPS URL. Настройте webhook на `https://<ваш-домен>/api/v1/telegram/webhook` с параметром `secret_token`, равным `TELEGRAM_WEBHOOK_SECRET`.
5. Запустите worker: `docker compose up --build`. В разделе «ML и проекты» создайте ссылку подключения и откройте её в Telegram.

Ссылка подключения одноразовая и действует 10 минут. Worker обрабатывает фоновые задания, повторяет временно неудачные попытки с задержкой и использует idempotency keys для предотвращения дублей. Перед реальными уведомлениями проверьте сценарий в тестовом Telegram-чате.

## Перед production

- Используйте HTTPS и `COOKIE_SECURE=true`.
- Задайте уникальные случайные секреты; не используйте локальные значения по умолчанию.
- Настройте домены OAuth callback точно под production URL.
- Проверьте права и revoke/disconnect flows, журнал ошибок, повторы и отсутствие дублей.
- Выполните тестовое восстановление резервной копии базы.
- Не используйте реальные данные учеников до прохождения security review и staging E2E-проверок.
