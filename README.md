# LifeOS

Personal Life Management System — планирование, задачи, привычки, цели, дневник, учёт времени и аналитика.

- [Product Requirements (PRD)](LifeOS%20Product%20Requirements.md) — **что** делает система.
- [System Design Document (SDD)](LifeOS%20System%20Design%20Document.md) — **как** это реализовано. Любое отклонение от SDD сначала вносится в SDD.

## Скриншоты

| Главная | Расписание — неделя |
| --- | --- |
| ![Главная](docs/screenshots/phase1-dashboard.png) | ![Неделя](docs/screenshots/phase1-week.png) |
| **День и свободное время** | **Задачи** |
| ![День](docs/screenshots/phase1-day.png) | ![Задачи](docs/screenshots/phase1-tasks.png) |
| **Карточка задачи** | **Тёмная тема** |
| ![Карточка задачи](docs/screenshots/phase1-task-drawer.png) | ![Тёмная тема](docs/screenshots/phase1-week-dark.png) |

<img src="docs/screenshots/phase1-mobile-tasks.png" alt="Задачи на телефоне" width="300">

<details><summary>Phase 0: вход, настройки</summary>

| Вход | Главная |
| --- | --- |
| ![Вход](docs/screenshots/01-login-light.png) | ![Главная](docs/screenshots/03-dashboard-light.png) |
| **Тёмная тема** | **Настройки** |
| ![Тёмная тема](docs/screenshots/06-dashboard-dark.png) | ![Настройки](docs/screenshots/04-settings-light.png) |

<img src="docs/screenshots/08-dashboard-mobile.png" alt="Мобильная версия" width="300">

</details>

## Статус: Phase 1 — Planning Core ✅

| Модуль | Что готово |
| --- | --- |
| Расписание | Виды «день / неделя / месяц / список»; 6 типов времени (`FIXED`, `FOCUS`, `PERSONAL`, `REST`, `BUFFER`, `FREE`); повторения (каждый день, по будням, еженедельно, ежемесячно, до даты) с виртуальным развёртыванием в часовом поясе события, в том числе через переход на летнее время; правка одного экземпляра, «этого и следующих» или всей серии; исключение экземпляра; перенос с причиной и историей; статусы «выполнено / пропущено / отменено» |
| Конфликты | Матрица SDD §6.3: два `FIXED` → `409 SCHEDULE_CONFLICT` с возможностью «сохранить всё равно» (`?force=true`), остальные пересечения — предупреждения; проверка ещё до сохранения |
| Свободное время | Рабочее окно профиля минус занятые блоки, окна от 15 минут; клик по окну создаёт событие |
| Задачи | Статусы с матрицей переходов (`409 INVALID_STATUS_TRANSITION`), приоритеты, сроки «до конца дня» в часовом поясе пользователя, оценка, категории и теги, подзадачи, перенос с причиной, история статусов, архив, мягкое удаление; блок времени в расписании для задачи |
| Входящие | Быстрый захват одной строкой, разбор («Разобрано» или назначение срока / категории / приоритета) |
| Категории | Создание, переименование, цвет, архив (Настройки → Категории) |
| Главная | Одна выдача `GET /dashboard/`: расписание дня, задачи на сегодня и просроченные, Входящие, свободное время, фокус и выполненные задачи |

## Phase 0 — Foundation ✅

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
  apps/schedule/     события, серии (RRULE), конфликты, свободное время
  apps/tasks/        задачи, подзадачи, история статусов, Входящие
  apps/dashboard/    агрегированная выдача главной страницы
frontend/src/
  app/               router, layouts, providers (i18n, query client)
  modules/           auth, dashboard, schedule, tasks, settings, placeholder (модули Phase 2+)
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

**Phase 2 — Personal Development:** Habits, Goals и Milestones, Journal, Time Tracking — по SDD §4.6–4.9.
