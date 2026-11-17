"""Test settings. Uses DATABASE_URL when given (CI: PostgreSQL), otherwise SQLite."""

import os

from .base import *  # noqa: F403
from .base import env

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production-use-only-000000"
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY

if not os.environ.get("DATABASE_URL"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "user": "10000/min",
    "auth": env("THROTTLE_AUTH", default="10000/min"),
    "ai": "10000/min",
}
REFRESH_COOKIE["secure"] = False
CELERY_TASK_ALWAYS_EAGER = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
LOGGING["root"]["level"] = "WARNING"

AI_ENABLED = True
AI_PROVIDER = "fake"  # deterministic scripted provider, never calls the network
