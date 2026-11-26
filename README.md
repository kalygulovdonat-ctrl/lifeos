# LifeOS

Personal Life Management System — планирование, задачи, привычки, цели, дневник, учёт времени и аналитика.

- [Product Requirements (PRD)](LifeOS%20Product%20Requirements.md) — **что** делает система.
- [System Design Document (SDD)](LifeOS%20System%20Design%20Document.md) — **как** это реализовано. Любое отклонение от SDD сначала вносится в SDD.

## Скриншоты

| Аналитика: неделя | Аналитика: месяц |
| --- | --- |
| ![Аналитика](docs/screenshots/phase3-analytics-week.png) | ![Месяц](docs/screenshots/phase3-analytics-month.png) |
| **AI-ассистент: черновик ждёт подтверждения** | **Обзор недели** |
| ![AI-ассистент](docs/screenshots/phase3-assistant.png) | ![Обзор недели](docs/screenshots/phase3-review.png) |
| **Самочувствие** | **Уведомления** |
| ![Самочувствие](docs/screenshots/phase4-wellness.png) | ![Уведомления](docs/screenshots/phase4-bell.png) |
| **Тёмная тема** | |
| ![Тёмная тема](docs/screenshots/phase3-analytics-dark.png) | |

<img src="docs/screenshots/phase3-mobile-assistant.png" alt="AI-ассистент на телефоне" width="300">

<details><summary>Phase 2: привычки, цели, дневник, время</summary>

| Привычки | Привычка: серии и тепловая карта |
| --- | --- |
| ![Привычки](docs/screenshots/phase2-habits.png) | ![Привычка](docs/screenshots/phase2-habit-detail.png) |
| **Цель и этапы** | **Учёт времени** |
| ![Цель](docs/screenshots/phase2-goal-detail.png) | ![Таймер](docs/screenshots/phase2-time.png) |
| **Дневник** | **Главная: привычки и цели** |
| ![Дневник](docs/screenshots/phase2-journal.png) | ![Главная](docs/screenshots/phase2-dashboard-widgets.png) |

<img src="docs/screenshots/phase2-mobile-habits.png" alt="Привычки на телефоне" width="300">

</details>

<details><summary>Phase 1: расписание и задачи</summary>

| Главная | Расписание — неделя |
| --- | --- |
| ![Главная](docs/screenshots/phase1-dashboard.png) | ![Неделя](docs/screenshots/phase1-week.png) |
| **День и свободное время** | **Задачи** |
| ![День](docs/screenshots/phase1-day.png) | ![Задачи](docs/screenshots/phase1-tasks.png) |
| **Карточка задачи** | **Тёмная тема** |
| ![Карточка задачи](docs/screenshots/phase1-task-drawer.png) | ![Тёмная тема](docs/screenshots/phase1-week-dark.png) |

<img src="docs/screenshots/phase1-mobile-tasks.png" alt="Задачи на телефоне" width="300">

</details>

<details><summary>Phase 0: вход, настройки</summary>

| Вход | Главная |
| --- | --- |
| ![Вход](docs/screenshots/01-login-light.png) | ![Главная](docs/screenshots/03-dashboard-light.png) |
| **Тёмная тема** | **Настройки** |
| ![Тёмная тема](docs/screenshots/06-dashboard-dark.png) | ![Настройки](docs/screenshots/04-settings-light.png) |

<img src="docs/screenshots/08-dashboard-mobile.png" alt="Мобильная версия" width="300">

</details>

## Статус: Phase 3–4 — Intelligence, Analytics и Experience ✅

| Модуль | Что готово |
| --- | --- |
| Аналитика | День, неделя, месяц с выбором периода. Метрики по формулам SDD §5 (версия формул `2026.1`): выполнение задач, регулярность привычек, часы фокуса, точность плана. У каждой метрики есть числитель и знаменатель, подсказка «Как считается» и сравнение с прошлым периодом. Нет данных → «Нет данных», а не 0%. Распределение времени по категориям, график по дням, привычки, цели, самочувствие. Месячный вид служит месячным отчётом. У каждого графика есть табличный вид |
| Обзор недели | Мастер из 4 шагов: итоги (снимок метрик фиксируется при завершении), решения по незакрытым задачам («перенести на следующую неделю», «назначить дату», «в бэклог», «отменить», «оставить»), рефлексия с оценкой недели, завершение. Один обзор на неделю, напоминание в конце недели |
| AI-ассистент | Claude (`claude-opus-5-5`) через официальный SDK. Ассистент читает только разрешённые разделы: согласия выдаются по разделам, а каждое чтение журналируется («Что видел AI»). Он **ничего не меняет сам**: создаёт черновики действий (задача, событие, подзадачи, отметка привычки, черновик дневника). Пользователь правит черновик, подтверждает или отклоняет его; выполненное действие можно отменить. Черновики истекают через 24 ч. Есть месячный лимит токенов, ограничение частоты, запросы идут через очередь Celery `ai` |
| Самочувствие | Отметки настроения, энергии и стресса (1–10), сон с качеством, графики за 30 дней, сигналы перегрузки (тяжёлые дни, недосып, стресс). Настроение и энергия из дневника сохраняются сюда (ADR-009) |
| Уведомления | Колокольчик со счётчиком непрочитанных. Напоминания (Celery beat), перегрузка, обзор недели, достигнутая цель. Старые уведомления удаляются автоматически |
| Языки и производительность | Русский встроен в основной бандл, английский и кыргызский подгружаются отдельными чанками при выборе. Библиотеки разнесены по чанкам: основной JS уменьшился с 728 до 360 kB. Все страницы адаптированы под телефон |

### AI-ассистент: как включить

AI выключен по умолчанию. Для работы с Claude в `backend/.env` (или окружении compose):

```bash
AI_ENABLED=true
ANTHROPIC_API_KEY=sk-ant-...
```

Без ключа работает демо-режим `AI_PROVIDER=fake` (в интерфейсе — значок «Демо»). Он работает без сети и понимает простые запросы: свободное время, план на завтра по приоритетам задач, «Задача: …» и «Событие: …» (черновики), привычки, цели, итоги недели. Отвечает по данным пользователя через те же инструменты и согласия, что и Claude. На нём же работают тесты и CI. Без Celery (локально без Docker) добавьте `AI_RUN_INLINE=true`.

## Phase 2 — Personal Development ✅

| Модуль | Что готово |
| --- | --- |
| Привычки | Типы «да/нет», количество, время, шкала; частота: каждый день, по дням недели, N раз в неделю/месяц, раз в N дней; цель «не меньше» или «не больше». Частота версионируется — изменение не переписывает прошлую статистику. Отметки неизменяемы: правка и отмена пишутся в историю. Повторная отметка дня — `409 HABIT_ALREADY_LOGGED`, количество и время за день суммируются. Паузы (отпуск, болезнь) и «отдых» не прерывают серию |
| Статистика привычек | Регулярность по формуле SDD §5.3 (сегодняшний день не считается до конца, отдых и паузы исключены, «N раз в неделю» считается по неделям), текущая и лучшая серия, тепловая карта за полгода |
| Цели | Иерархия до 6 уровней без циклов (видение → год → квартал → месяц), прогресс по показателю (в том числе убывающему), по этапам с весами, по связанным задачам или вручную; история прогресса и статусов. 100% не завершает цель сама — приложение предлагает подтвердить |
| Дневник | «Итоги дня» по шаблону из 7 вопросов (любые можно пропустить, одна запись на день) и свободные записи; поиск; записи приватны и не попадают в аудит и логи |
| Учёт времени | Один активный таймер (`409 TIMER_ALREADY_RUNNING`), пауза и продолжение, состояние хранится на сервере и переживает перезагрузку; ручные записи с защитой от дублей и будущего времени, правки с историей; план против факта за неделю, фокус-время. Таймер виден на всех страницах |
| Связи | Задача показывает фактическое время и цели, в карточке задачи — кнопка таймера; выполнение задачи пересчитывает прогресс связанных целей; на главной — привычки дня, активные цели, учтённое время и активный таймер |

## Phase 1 — Planning Core ✅

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

## Размещение на Render (бесплатно)

`render.yaml` описывает демо-размещение: один веб-сервис (Django отдаёт и API, и собранный React, `infra/docker/Dockerfile.render`) и бесплатная PostgreSQL. В Render: **New → Blueprint**, выбрать этот репозиторий, **Apply**. Ограничения бесплатного плана: сервис засыпает после ~15 минут простоя (первое открытие ~1 минута), бесплатная база удаляется через 30 дней, фонового воркера нет — ИИ работает в запросе (`AI_RUN_INLINE`), напоминания по расписанию не отправляются.

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
  apps/habits/       привычки, версии частоты, отметки, паузы, серии и регулярность
  apps/goals/        цели, этапы, связь с задачами, история прогресса
  apps/journal/      итоги дня и свободные записи
  apps/time_tracking/ таймер, записи времени, план против факта
  apps/dashboard/    агрегированная выдача главной страницы
  apps/analytics/    метрики дня, недели и месяца (SDD §5)
  apps/reviews/      обзор недели, решения по задачам
  apps/wellness/     самочувствие, сон, сигналы перегрузки
  apps/notifications/ напоминания и уведомления
  apps/ai_assistant/ провайдеры (Anthropic, демо), инструменты, черновики действий
frontend/src/
  app/               router, layouts, providers (i18n, query client)
  modules/           auth, dashboard, schedule, tasks, habits, goals, journal, time, analytics, reviews, wellness, assistant, notifications, settings
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

## Что дальше

Все четыре фазы PRD собраны. Дальше: P1-функции, которые SDD откладывает (вложения в дневнике, `goal_habit`, полнотекстовый поиск, GiST-ограничения для PostgreSQL), и запуск в продакшене (`infra/`, бэкапы, мониторинг).

## Автор и лицензия
Автор — [kalygulovdonat-ctrl](https://github.com/kalygulovdonat-ctrl). © 2026, все права защищены.
Копировать этот код в другие репозитории, публиковать его и выдавать за свою работу без разрешения автора запрещено.
Подробности — в файле [LICENSE](LICENSE).
