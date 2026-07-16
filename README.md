# LinkCutter

Сервис коротких ссылок с гостевым режимом, личным кабинетом, базовой
статистикой и защищённой административной модерацией. Backend находится в
`src/`, React frontend — в `frontend/`.

## Возможности

- гостевое создание ссылок без регистрации;
- домены без схемы автоматически получают `https://`;
- безопасная проверка URL и запрет credentials/localhost/private literal IP;
- регистрация, подтверждение email, login, refresh/logout и восстановление пароля;
- Argon2-хэши паролей, JWT access tokens и отзываемые refresh tokens;
- личные ссылки с режимами `reuse` и `new`;
- пагинация, фильтры, label, активность и базовая статистика;
- admin API для пользователей и всех гостевых/личных ссылок;
- неизменяемые целевой URL, shortcode и владелец ссылки;
- SQLite как источник истины и Redis как необязательный кэш;
- healthcheck, Docker Compose, Ruff, pytest и GitHub Actions.

Гостевая статистика не публикуется. Администратор может отключить ссылку или
изменить label, но не может подменить её назначение.

## Swagger

Интерактивная документация: `http://localhost:8000/docs`.

OpenAPI JSON: `http://localhost:8000/openapi.json`.

## Интерфейс

Frontend доступен на `http://localhost:3000`. Гость может сразу сократить
ссылку; после входа доступны личные ссылки, папки, аналитика, настройки,
профиль и уведомления. URL и shortcode нельзя изменить. Если пользователь
пытается создать уже существующий URL, интерфейс предлагает использовать
существующую ссылку или создать новую кампанию с отдельной статистикой.

В Swagger защищённые операции используют кнопку `Authorize`. В неё передаётся
только значение access token; префикс Bearer интерфейс добавляет автоматически.

## API

### Общие операции

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/v1/links` | Создать гостевую или личную ссылку |
| `GET` | `/{shortcode}` | Редирект `307` и запись перехода |
| `GET` | `/health/live` | Проверить работу процесса |
| `GET` | `/health/ready` | Проверить SQLite и Redis |

Гостевой запрос:

```json
{
  "url": "google.com"
}
```

`google.com` нормализуется в `https://google.com/`. Повторный гостевой URL
возвращает тот же shortcode с `200 OK` и `created: false`.

Авторизованный запрос:

```json
{
  "url": "https://example.com/campaign",
  "mode": "new",
  "label": "Реклама у блогера A"
}
```

`reuse` возвращает активную ссылку владельца для этого URL. `new` создаёт новый
shortcode с отдельной статистикой.

### Авторизация

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Зарегистрировать пользователя |
| `POST` | `/api/v1/auth/verify-email` | Подтвердить email |
| `POST` | `/api/v1/auth/login` | Получить access и refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Ротировать refresh token |
| `POST` | `/api/v1/auth/logout` | Отозвать refresh token |
| `POST` | `/api/v1/auth/password-reset/request` | Запросить сброс пароля |
| `POST` | `/api/v1/auth/password-reset/confirm` | Установить новый пароль |
| `GET` | `/api/v1/me` | Получить текущего пользователя |

Access token короткоживущий. Refresh token хранится в SQLite только как SHA-256
хэш, ротируется при использовании и отзывается при logout или смене пароля.

Пока email-провайдер не подключён, development-окружение возвращает одноразовый
verification/reset token в ответе. В production эти поля скрываются.

### Личный кабинет

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/v1/me/links` | Свои ссылки с пагинацией и фильтрами |
| `GET` | `/api/v1/me/links/{shortcode}` | Ссылка и базовая статистика |
| `PATCH` | `/api/v1/me/links/{shortcode}` | Изменить `label` или `is_active` |

Ответ содержит исходный и короткий URL, статус, label, число переходов, дату
создания, дату обновления и последний переход. Чужая ссылка отвечает `404`.
Поля URL и shortcode отсутствуют в PATCH-модели.

### Администрация

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/v1/admin/users` | Все пользователи |
| `GET` | `/api/v1/admin/users/{user_id}` | Конкретный пользователь |
| `PATCH` | `/api/v1/admin/users/{user_id}` | Статус аккаунта и роль admin |
| `GET` | `/api/v1/admin/links` | Все гостевые и личные ссылки |
| `GET` | `/api/v1/admin/links/{shortcode}` | Любая ссылка и статистика |
| `PATCH` | `/api/v1/admin/links/{shortcode}` | Модерация `label/is_active` |

Роль назначается при регистрации, если email находится в `ADMIN_EMAILS`.
Публичного параметра `is_admin` в регистрации нет. Активный администратор не
может отключить или понизить собственный аккаунт.

## Локальный запуск

Требуются Python 3.11+ и, опционально, Redis.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn main:app --app-dir src --reload
```

Без Redis приложение продолжает работать; readiness сообщает `degraded`.

В отдельном терминале запустите интерфейс:

```bash
cd frontend
npm ci
npm run dev
```

## Docker Compose

```bash
docker compose up --build
```

Интерфейс публикуется на `127.0.0.1:${FRONTEND_PORT:-3000}`, Swagger — на
`127.0.0.1:${APP_PORT:-8000}/docs`. Nginx проксирует API и короткие коды в
FastAPI, поэтому переход на несуществующий код показывает страницу 404. SQLite
и Redis используют отдельные Docker volumes.

## Ошибки

Обычная ошибка:

```json
{
  "code": "link_not_found",
  "detail": "Short link not found"
}
```

Ошибка валидации дополнительно содержит `errors`. Основные коды:
`validation_error`, `link_not_found`, `link_disabled`,
`authentication_required`, `invalid_access_token`, `invalid_refresh_token`,
`invalid_credentials`, `email_not_verified`, `admin_required`,
`storage_unavailable` и `shortcode_unavailable`.

## Конфигурация

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `PUBLIC_BASE_URL` | Публичный адрес коротких ссылок | `http://localhost:8000` |
| `DATABASE_PATH` | SQLite database | `data/links.db` |
| `REDIS_URL` | Redis | `redis://localhost:6379/0` |
| `CACHE_TTL_SECONDS` | TTL кэша | `3600` |
| `AUTH_SECRET_KEY` | Секрет подписи JWT | dev-only |
| `ACCESS_TOKEN_MINUTES` | Жизнь access token | `15` |
| `REFRESH_TOKEN_DAYS` | Жизнь refresh token | `30` |
| `EMAIL_VERIFICATION_HOURS` | Жизнь verification token | `24` |
| `PASSWORD_RESET_MINUTES` | Жизнь reset token | `30` |
| `ADMIN_EMAILS` | Email будущих администраторов | `[]` |
| `CORS_ORIGINS` | Разрешённые frontend origins | localhost:3000 |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

В production необходимо заменить `AUTH_SECRET_KEY`; приложение откажется
запускаться со стандартным development-секретом.

## Архитектура

```text
HTTP API -> AuthService -> SQLite
         -> LinkService -> SQLite
                        \-> Redis cache
```

SQLite хранит пользователей, хэши refresh/action tokens, владение ссылками и
агрегированную статистику. Redis ускоряет редиректы, но не является источником
истины.

## Проверки

```bash
ruff check .
pytest
```

Те же проверки выполняются в GitHub Actions.

## Дальнейший план

1. Подключить email-провайдера.
2. Добавить rate limiting и защиту auth endpoints от перебора.
3. Добавить жалобы, admin audit log и причины блокировки.
4. Перейти на PostgreSQL и Alembic перед масштабированием.
5. Добавить метрики, резервные копии и error tracking.

## Лицензия

MIT
