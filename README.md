# URL Shortener API

API для создания коротких ссылок. Сейчас реализован первый этап: надёжный
гостевой сценарий без регистрации. Пользователь отправляет длинный URL,
получает короткий адрес и может сразу им поделиться.

## Что уже работает

- создание ссылки через JSON API;
- строгая проверка `http` и `https` URL;
- запрет credentials, localhost и private/reserved literal IP;
- общий shortcode для одинаковых гостевых URL;
- редирект по короткому коду;
- атомарный счётчик переходов;
- постоянное хранение в SQLite;
- Redis как необязательный кэш с fallback на SQLite;
- liveness и readiness endpoints;
- локальный запуск и Docker Compose;
- автоматические тесты, lint и CI.

Гостевая статистика не публикуется. Изменение назначения и удаление ссылки
также недоступны: безопасное управление появится вместе с аккаунтами и
проверкой владельца.

## API

Swagger показывает только уже работающий API первого этапа:

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/v1/links` | Создать или повторно получить гостевую ссылку |
| `GET` | `/{shortcode}` | Выполнить редирект и записать переход |
| `GET` | `/health/live` | Проверить работу процесса |
| `GET` | `/health/ready` | Проверить SQLite и Redis |

Регистрация, вход, кабинет и `/api/v1/me/*` перечислены ниже как дальнейший
план и пока намеренно отсутствуют в Swagger.

### Создать короткую ссылку

```http
POST /api/v1/links
Content-Type: application/json

{
  "url": "https://example.com/long/path"
}
```

Новая ссылка возвращает `201 Created`:

```json
{
  "shortcode": "aB3dE7xQ",
  "short_url": "http://localhost:8000/aB3dE7xQ",
  "created": true
}
```

Если гость повторно отправляет тот же нормализованный URL, API возвращает
существующий shortcode с `200 OK` и `created: false`.

### Перейти по короткой ссылке

```http
GET /{shortcode}
```

Рабочая ссылка отвечает `307 Temporary Redirect`. Неизвестный shortcode
возвращает `404 Not Found`; зарезервированная, но отключённая ссылка —
`410 Gone`.

### Состояние сервиса

```http
GET /health/live
GET /health/ready
```

SQLite обязателен для readiness. Если Redis недоступен, сервис отвечает как
`degraded`, но продолжает создавать ссылки и выполнять редиректы через SQLite.

Интерактивная документация доступна по `/docs`, OpenAPI-схема — по
`/openapi.json`.

Для удобства гостевой API принимает как полный URL, так и домен без схемы:
`google.com` автоматически обрабатывается как `https://google.com/`.

## Локальный запуск

Требуются Python 3.11+ и, опционально, Redis.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn main:app --app-dir src --reload
```

Без Redis приложение продолжит работать, но readiness покажет состояние
кэша `down`.

## Docker Compose

```bash
docker compose up --build
```

API будет доступен на `http://localhost:8000` и на первом этапе привязан только
к `127.0.0.1`. Redis запускается отдельным сервисом, а файл SQLite хранится в
Docker volume.

## Ошибки

Обычные ошибки API содержат стабильный машинный код:

```json
{
  "code": "link_not_found",
  "detail": "Short link not found"
}
```

Основные коды: `validation_error`, `link_not_found`, `link_disabled`,
`storage_unavailable` и `shortcode_unavailable`. Ошибка валидации дополнительно
содержит массив `errors` с расположением и типом каждого нарушения.

## Проверки

```bash
ruff check .
pytest
```

Эти же проверки выполняются в GitHub Actions для каждого push и pull request.

## Конфигурация

Основные переменные окружения:

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `PUBLIC_BASE_URL` | Публичный адрес коротких ссылок | `http://localhost:8000` |
| `DATABASE_PATH` | Путь к SQLite | `data/links.db` |
| `REDIS_URL` | Адрес Redis | `redis://localhost:6379/0` |
| `CACHE_TTL_SECONDS` | Время жизни записи кэша | `3600` |
| `CORS_ORIGINS` | Разрешённые frontend origins в JSON | localhost:3000 |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

## Архитектура

```text
HTTP API -> LinkService -> SQLite
                    \-> Redis cache
```

SQLite является источником истины. Redis ускоряет редиректы, но его отказ не
должен останавливать сервис. В таблице ссылок уже предусмотрены `owner_id`,
`label` и `is_active` для следующего этапа.

## Дальнейший план

1. Добавить аккаунты с email/password, подтверждением почты и восстановлением
   доступа.
2. Добавить личный кабинет: собственные ссылки, названия, включение/отключение
   и базовая статистика.
3. Разрешить владельцу выбирать между повторным использованием своей ссылки и
   новым shortcode с отдельной статистикой кампании.
4. Перед публичным запуском добавить rate limiting, защиту от злоупотреблений и
   административную модерацию.
5. При масштабировании перейти на PostgreSQL и управляемые миграции.

Целевой URL пользовательской ссылки после создания изменять нельзя.

## Лицензия

MIT
