COMPOSE := docker compose -f infra/compose/docker-compose.yml
BACKEND := $(COMPOSE) exec backend

.PHONY: up down logs migrate makemigrations superuser shell test test-backend test-frontend lint schema api-types backup

up:            ## Start the full local stack (Postgres, Redis, Django, Celery, Vite, Mailpit)
	$(COMPOSE) up --build -d
	@echo "Frontend: http://localhost:5173  API: http://localhost:8000/api/v1/  Mail: http://localhost:8025"

down:          ## Stop the local stack
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f backend worker frontend

migrate:
	$(BACKEND) python manage.py migrate

makemigrations:
	$(BACKEND) python manage.py makemigrations

superuser:
	$(BACKEND) python manage.py createsuperuser

shell:
	$(BACKEND) python manage.py shell

test: test-backend test-frontend

test-backend:
	cd backend && python -m pytest

test-frontend:
	cd frontend && npm test

lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint && npm run typecheck && npm run format:check && npm run i18n:check

schema:        ## Export OpenAPI schema to backend/schema.yml
	cd backend && DJANGO_SETTINGS_MODULE=config.settings.test python manage.py spectacular --validate --file schema.yml

api-types: schema  ## Regenerate frontend API types from the OpenAPI schema
	cd frontend && npm run api:types

backup:
	sh infra/scripts/backup.sh
