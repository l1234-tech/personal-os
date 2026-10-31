# Google Calendar и библиотека материалов

## Google Calendar

Интеграция работает через OAuth 2.0 и использует отдельные настройки Google Cloud. Для локального запуска:

1. В Google Cloud выбери проект Personal OS.
2. Включи Google Calendar API.
3. В Google Auth Platform настрой OAuth consent screen. Для личного использования оставь режим Testing и добавь свой Google-аккаунт в Test users.
4. Создай OAuth Client ID типа Web application.
5. Добавь Authorized JavaScript origin: \`http://localhost:5173\`.
6. Добавь Authorized redirect URI: \`http://localhost:8000/api/v1/integrations/google/callback\`.
7. Заполни локальный файл \`.env\` в корне проекта:

\`\`\`env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/integrations/google/callback
TOKEN_ENCRYPTION_KEY=...
\`\`\`

Сгенерировать Fernet key можно локально командой Python (ключ не отправлять в GitHub и никому не пересылать):

\`\`\`powershell
python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
\`\`\`

Сохрани результат в \`TOKEN_ENCRYPTION_KEY\`. Не добавляй реальные OAuth credentials или ключ шифрования в репозиторий. \`.env.example\` содержит только пустые шаблонные значения.

После заполнения \`.env\` пересобери сервисы:

\`\`\`powershell
docker compose down
docker compose up --build -d
docker compose logs -f api
\`\`\`

В приложении открой **Google Calendar → Подключить Google Calendar**, выбери аккаунт и подтверди доступ. Затем выбери нужные календари и нажми **Сохранить выбор → Синхронизировать события**.

События Google импортируются в Personal OS. Личные события можно вручную опубликовать в выбранный календарь с экрана Google Calendar. Для записи требуется scope `calendar.events`; после обновления scope существующее подключение нужно отключить и подключить заново, чтобы Google выдал новые разрешения. Перед обновлением опубликованного события Personal OS сравнивает сохранённый ETag с текущей версией в Google. Если событие изменилось вне Personal OS, отправка блокируется со статусом конфликта — внешние изменения не перезаписываются автоматически. Удаление событий в Google из Personal OS пока не поддерживается. Токены сохраняются в базе в зашифрованном виде. Для локального OAuth в режиме Testing Google-аккаунт должен быть добавлен в Test users.

## Библиотека

Открой **Библиотека → Импорт JSON** и выбери файл резервной копии \`uchebnaya-biblioteka-backup.json\`, экспортированный из старой HTML-библиотеки. Записи будут сохранены в localStorage текущего браузера. Данные не отправляются на backend и не публикуются в GitHub.

Доступны поиск, фильтр по типу, избранное, добавление, редактирование, удаление, импорт и экспорт JSON. Встроенные быстрые ссылки на К. Полякова, Школково, Решу ЕГЭ и Решу ОГЭ доступны сразу.

**Ограничения локальных путей:** ссылки вида \`C:\\Users\\Lenovo\\...\` и \`file:///\` указывают на файлы именно на твоём компьютере. Браузер может блокировать открытие локального файла со страницы приложения. Для папок проектов предусмотрено открытие через протокол \`vscode://file\`; для обычных локальных файлов при необходимости используй исходный путь. Сами PDF/файлы в Personal OS не загружаются.
