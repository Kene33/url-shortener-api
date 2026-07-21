<div align="center">
  <img src="./docs/readme-assets/logo.svg" alt="Логотип LinkCutter" width="220" />
  <h1>LinkCutter</h1>
  <p><strong>Сервис коротких ссылок с гостевым режимом, личным кабинетом, аналитикой и админ-разделом.</strong></p>
  <p>
    <a href="https://url-shortener-wheat-three.vercel.app">Live demo</a>
    ·
    <a href="https://url-shortener-api-three.vercel.app/docs">Swagger UI</a>
    ·
    <a href="./README.md">English</a>
    ·
    <a href="./README.ru.md"><strong>Русский</strong></a>
  </p>
  <p>
    <a href="#быстрый-старт">Быстрый старт</a>
    ·
    <a href="#возможности">Возможности</a>
    ·
    <a href="#проверка">Проверка</a>
    ·
    <a href="./CONTRIBUTING.md">Участие</a>
    ·
    <a href="./SECURITY.md">Безопасность</a>
  </p>
  <p>
    <img alt="CI" src="https://github.com/Kene33/url-shortener/actions/workflows/ci.yml/badge.svg" />
    <img alt="Лицензия" src="https://img.shields.io/github/license/Kene33/url-shortener?color=0f766e" />
    <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" />
    <img alt="React 19" src="https://img.shields.io/badge/React-19-20232A?logo=react&logoColor=61DAFB" />
  </p>
</div>

LinkCutter состоит из FastAPI API и React-приложения. Гости сокращают ссылки без регистрации. Пользователи получают папки, статистику, настройки и уведомления. Администратор управляет пользователями, ссылками и сроком жизни ссылок удалённых аккаунтов.

## Почему LinkCutter

- Гость сокращает ссылку без регистрации.
- Пользователь получает личный кабинет с названиями, папками, счётчиком переходов и базовой аналитикой.
- Владелец и staff не могут изменить исходный URL или shortcode.
- Роли staff покрывают модерацию, жалобы, audit log, retention-настройки и анонимизацию аккаунтов.
- Подтверждение email и email 2FA доступны через API, но не обязательны в pet-проекте.

## Live Demo

- Frontend: [url-shortener-wheat-three.vercel.app](https://url-shortener-wheat-three.vercel.app)
- Backend health: [health/ready](https://url-shortener-api-three.vercel.app/health/ready)
- Swagger UI: [url-shortener-api-three.vercel.app/docs](https://url-shortener-api-three.vercel.app/docs)

Production использует Neon PostgreSQL и Upstash Redis. Новые аккаунты и ссылки сохраняются между перезапусками.

## Скриншоты

<p align="center">
  <img src="./docs/screenshots/home.png" alt="Гостевой экран сокращения ссылки" width="900" />
</p>

### Кабинет

| Мои ссылки | Аналитика | Папки |
| --- | --- | --- |
| ![Мои ссылки](./docs/screenshots/links.png) | ![Аналитика](./docs/screenshots/analytics.png) | ![Папки](./docs/screenshots/folders.png) |

| Уведомления | Настройки | Профиль |
| --- | --- | --- |
| ![Уведомления](./docs/screenshots/notifications.png) | ![Настройки](./docs/screenshots/settings.png) | ![Профиль](./docs/screenshots/profile.png) |

## Возможности

- Гостевое сокращение с нормализацией URL и повторным использованием уже созданной гостевой ссылки.
- Регистрация, подтверждение email, вход, обновляемая сессия, выход, сброс пароля и подготовленный сценарий email 2FA.
- Личные ссылки с папками, названием, включением и отключением. URL назначения и shortcode не редактируются.
- Агрегированная аналитика без IP, географии, устройства и referrer.
- Профиль, аватар, тема, язык, уведомления, экспорт данных и отложенное удаление аккаунта с отменой в течение 30 дней.
- Подтверждение email и двухэтапный вход по email доступны через API, но по умолчанию не обязательны.
- Роли `support`, `moderator`, `admin`, dashboard, жалобы, история модерации, audit log и retention-настройки доступны через `/api/v1/admin/*`.
- Админские маршруты для модерации пользователей и ссылок, а также настройки срока работы ссылок удалённых аккаунтов.

## Сравнение

| Возможность | Минимальный shortener | LinkCutter | Полный SaaS-shortener |
| --- | --- | --- | --- |
| Гостевое сокращение | Обычно да | Да | Обычно да |
| Личный кабинет | Редко | Да | Да |
| Неизменяемый исходный URL | Часто неясно | Да | Зависит от сервиса |
| Аналитика владельца | Редко | Базовая | Расширенная |
| Модерация и жалобы | Редко | Admin API | Обычно есть |
| Локальная разработка | Иногда | Docker Compose, SQLite, Redis | Зависит от сервиса |

## Быстрый старт

### Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

После запуска:

- приложение: `http://127.0.0.1:3000`
- Swagger: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

Первый результат: откройте frontend, вставьте `https://example.com`, создайте короткую ссылку и перейдите по ней. Swagger находится на `http://127.0.0.1:8000/docs`.

### Локальная разработка

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn main:app --app-dir src --reload
```

Frontend, во втором терминале:

```bash
cd frontend
npm ci
npm run dev
```

Vite работает на `http://127.0.0.1:3000` и проксирует `/api` и `/health` на backend по адресу `http://127.0.0.1:8000`.

### Демо-данные

Команда создаёт локальные проверенные аккаунты, папки, ссылки, уведомления и агрегированную статистику. В production она завершается ошибкой.

```bash
DEMO_SEED_PASSWORD='DemoPass123!' PYTHONPATH=src python -m app.demo_seed
```

Учётные записи: `demo-admin@example.com` и `demo-user@example.com`. Пароль - значение `DEMO_SEED_PASSWORD`.

## Проверка

```bash
PYTHONPATH=src ruff check .
PYTHONPATH=src pytest
cd frontend && npm run lint
cd frontend && npm test -- --run
cd frontend && npm run build
cd frontend && npm run test:e2e
```

GitHub Actions выполняет эти проверки для push и pull request.

## Статус production

| Область | Статус |
| --- | --- |
| Гостевое сокращение и redirect | Развёрнуто |
| Личный кабинет и аналитика | Развёрнуты |
| Admin moderation API | Развёрнут |
| Frontend | Vercel |
| База данных | Neon PostgreSQL через Vercel Marketplace |
| Кэш и rate limit | Upstash Redis через Vercel Marketplace |
| Email provider | Не обязателен по умолчанию |
| Alembic-миграции | Следующий этап |

Подтверждение email, сброс пароля и email 2FA требуют почтового провайдера после включения в production.

## Документы

- [README на английском](./README.md)
- [История изменений](./CHANGELOG.md)
- [Правила участия](./CONTRIBUTING.md)
- [Политика безопасности](./SECURITY.md)

## Лицензия

[MIT](./LICENSE)
