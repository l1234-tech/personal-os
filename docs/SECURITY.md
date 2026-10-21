# Безопасность

## Обязательные правила
- Закрытая регистрация: invite token cryptographically random, одноразовый, с TTL; хранить hash токена.
- Пароли — современный password hashing, никогда не писать пароль в лог.
- Сессии по безопасной схеме (предпочтительно HttpOnly/Secure/SameSite cookies для same-site web); долгоживущие credentials не хранить в localStorage.
- Rate limit на вход, регистрацию и проверку приглашений.
- Каждый read/write/delete ограничен ownership/workspace membership на backend. Нельзя доверять скрытым кнопкам в UI.
- OAuth scopes по минимуму; tokens encrypted at rest, ключ вне БД и git; ревокация доступна.
- Secrets только в environment/secret manager, не в Git, клиентской сборке, traceback или логах.
- HTTPS/security headers в production; CORS только для настроенных origins.
- Внешние записи требуют подтверждения; важные изменения идут в audit log без секретных значений.
- Backups encrypted и отдельно; тестировать восстановление на отдельном экземпляре.
- Fixtures — синтетические. Не передавать заметки AI-сервисам без явного согласия.
- Агент не выполняет production deploy, разрушительные миграции или удаление данных без подтверждения.

## Перед production
Создать случайные секреты, выключить debug, настроить TLS/CORS/rate limits, проверить ownership-тесты, добавить dependency/container scanning, настроить ротацию/отзыв OAuth credentials и провести restore drill. Не использовать foundation-каркас для настоящих личных данных до реализации auth и доменной авторизации.
