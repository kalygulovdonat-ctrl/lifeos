# LifeOS

Personal Life Management System — планирование, задачи, привычки, цели, дневник, учёт времени и аналитика.

- [Product Requirements (PRD)](LifeOS%20Product%20Requirements.md) — **что** делает система.
- [System Design Document (SDD)](LifeOS%20System%20Design%20Document.md) — **как** это реализовано. Любое отклонение от SDD сначала вносится в SDD.

## Статус: Phase 0 — Foundation ✅

| Область | Что готово |
| --- | --- |
| Backend | Django 5.2 + DRF, modular monolith (`apps/`, `common/`), настройки local / test / production, Celery + beat |
| Аутентификация | Регистрация, вход, выход, смена пароля. Access JWT — только в памяти фронтенда; refresh JWT — в `HttpOnly` cookie с ротацией и blacklist; CSRF (double submit) на cookie-эндпоинтах |
| Профиль | Часовой пояс (IANA), язык `ru`/`en`/`ky`, 12/24 ч, начало недели, тема, рабочее окно дня |
| Справочники | Категории (8 системных при регистрации) и теги, с изоляцией по пользователю |
| Общий слой | Единый формат ошибок, UUID v7, audit log, `Idempotency-Key`, request id, JSON-логи с маскировкой секретов, health checks, модуль времени (`period_bounds` с учётом DST) |
| Frontend | React 19 + TypeScript strict + Vite, React Router 7, TanStack Query, Zustand, RHF + Zod, i18next (RU/EN/KY), светлая/тёмная тема, адаптивный layout, вход/регистрация/главная/настройки, заглушки модулей следующих фаз |
| Инфраструктура | Docker Compose (Postgres, Redis, Django, Celery worker/beat, Vite, Mailpit), production compose + nginx (WhiteNoise для статики админки), скрипты backup/restore. Проверено локально: dev- и prod-стеки поднимаются, e2e проходит на контейнерах |
| CI | GitHub Actions: lint, migrations check, pytest на PostgreSQL (порог покрытия 80%), OpenAPI validate, фронтенд lint/typecheck/i18n/test/build, security (pip-audit, bandit, npm audit, gitleaks), Playwright e2e, сборка образов |

## Быстрый старт

### С Docker (рекомендуется)

```bash
make up
```

Frontend — http://localhost:5173, API — http://localhost:8000/api/v1/, Swagger — http://localhost:8000/api/v1/docs/, письма — http://localhost:8025.

### Без Docker (SQLite)

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements/dev.txt   # Linux/macOS: .venv/bin/pip
cp .env.example .env
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py runserver
```

```bash
cd frontend
npm install
npm run dev
```

Vite проксирует `/api` на `http://localhost:8000`, поэтому frontend и API работают с одного origin (cookie и CSRF без CORS).

### Без Docker, но с PostgreSQL (Windows, без прав администратора)

Портативные бинарники PostgreSQL 16 (EDB, `postgresql-16.x-1-windows-x64-binaries.zip`) распакованы в `%LOCALAPPDATA%\lifeos-tools\pgsql`, кластер — `%LOCALAPPDATA%\lifeos-tools\pgdata` (localhost:5432, `lifeos`/`lifeos`).

```bash
powershell -File infra/scripts/local-postgres.ps1 start
```

```bash
cd backend && DATABASE_URL=postgres://lifeos:lifeos@localhost:5432/lifeos .venv/Scripts/python -m pytest
```

Чтобы dev-сервер работал на PostgreSQL, замените `DATABASE_URL` в `backend/.env`.

## Проверки

```bash
cd backend && .venv/Scripts/python -m pytest
```

```bash
cd frontend && npm test && npm run lint && npm run typecheck && npm run i18n:check
```

E2E (нужен запущенный стек `make up`):

```bash
cd frontend && npx playwright install chromium && npm run e2e
```

## Структура

```
backend/
  config/            settings (base/local/test/production), urls, celery
  common/            ошибки, базовые модели, audit, idempotency, время, логи, health
  apps/accounts/     пользователь, профиль, категории, теги, JWT-аутентификация
frontend/src/
  app/               router, layouts, providers (i18n, query client)
  modules/           auth, dashboard, settings, placeholder (остальные модули — Phase 1+)
  shared/            api-клиент, store, компоненты, хуки, утилиты времени
  locales/{ru,en,ky}/
infra/               Dockerfiles, nginx, compose, backup/restore
.github/workflows/   CI
```

## Правила разработки (кратко из SDD)

- Views без бизнес-логики → `services` (запись, транзакции) и `selectors` (чтение, всегда с фильтром по `user`).
- Чужой объект → **404**. Каждый новый эндпоинт добавляется в `backend/tests/test_isolation.py`.
- Все моменты времени — UTC (`timestamptz`); локальные даты — через `common.time`. `datetime.now()` / `date.today()` в бизнес-коде запрещены.
- В БД — стабильные коды (`TODO`, `FOCUS`), переводы — только во frontend (`errors.<CODE>`, `tasks:status.TODO`).
- Новые ключи переводов добавляются во все три языка — `npm run i18n:check` проверяет полноту.

## Следующий шаг

**Phase 1 — Planning Core:** Schedule (события, серии, конфликты, свободное время), Tasks (статусы, подзадачи, Inbox, история), Dashboard-виджеты — по SDD §4.4–4.5, §6.3, §7.2.
