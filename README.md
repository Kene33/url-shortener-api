# URL Shortener API

Сервис сокращения URL, построенный на FastAPI, Redis и SQLite.

## Возможности

- Создание коротких URL со случайными кодами
- Перенаправление на оригинальные URL по коротким кодам
- Отслеживание статистики доступа к URL
- Удаление сокращенных URL
- Постоянное хранение в SQLite
- Быстрое кэширование с Redis
- Поддержка Docker
- Включен CORS

## Технологический стек

- Python 3.11+
- FastAPI - веб-фреймворк
- Redis - уровень кэширования
- SQLite - постоянное хранилище
- Uvicorn - ASGI сервер
- Docker - контейнеризация

## API Endpoints

| Метод | Endpoint | Описание |
|--------|----------|-------------|
| POST | `/api/links/{url}` | Создать новый сокращенный URL |
| GET | `/{shortcode}` | Перенаправление на оригинальный URL |
| GET | `/api/links/{shortcode}/stats` | Получить статистику URL |
| DELETE | `/api/links/{shortcode}` | Удалить сокращенный URL |

## Начало работы

### Предварительные требования

- Python 3.11 или выше
- Redis сервер
- Docker (опционально)

### Локальная разработка

1. Клонировать репозиторий:
```bash
git clone https://github.com/Kene33/url-shortener-api.git
cd url-shortener-api
```

2. Создать и активировать виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate
```

3. Установить зависимости:
```bash
pip install -r requirements.txt
```

4. Запустить Redis сервер

5. Запустить приложение:
```bash
python src/main.py
```

API будет доступен по адресу `http://127.0.0.1:8000`

### Использование Docker

1. Собрать Docker образ.

2. Запустить контейнер.

## Тестирование

Для заполнения базы данных тестовыми данными:

```bash
python scripts/seed_db.py
```

## Примеры использования API

### Создание короткого URL

```bash
curl -X POST "http://localhost:8000/api/links/https://example.com"
```

Ответ:
```json
{
    "ok": true,
    "key": "abc123"
}
```

### Получение статистики URL

```bash
curl "http://localhost:8000/api/links/abc123/stats"
```

Ответ:
```json
{
    "ok": true,
    "id": 1,
    "url": "https://example.com",
    "shortcode": "abc123",
    "createdAt": "2024-02-20 10:30:00",
    "updatedAt": "2024-02-20 10:30:00",
    "accessCount": 5
}
```

## Структура проекта

```
├── src/
│   ├── main.py           # Точка входа в приложение
│   └── app/
│       ├── api/          # API маршруты
│       ├── db/           # Модули базы данных
│       │   ├── redis/    # Redis клиент
│       │   └── sql/      # SQLite клиент
│       └── utils/        # Вспомогательные функции
├── scripts/              # Вспомогательные скрипты
├── requirements.txt      # Зависимости
└── Dockerfile           
```
## TODO

### Первоочередные задачи
- [ ] Добавить валидацию URL
- [ ] Реализовать rate limiting для API endpoints
- [ ] Добавить аутентификацию пользователей
- [ ] Написать unit тесты

### Улучшения
- [ ] Добавить документацию API
- [ ] Добавить логирование
- [ ] Оптимизировать кэширование в Redis
- [ ] Добавить поддержку кастомных shortcode'ов

### Инфраструктура
- [ ] Настроить Docker Compose
- [ ] Добавить healthcheck endpoints
- [ ] Настроить резервное копирование базы данных
- [ ] Реализовать масштабирование с использованием Kubernetes


## Лицензия

MIT License