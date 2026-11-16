"""Production (cloud) settings. All secrets must come from the environment."""

from .base import *  # noqa: F403
from .base import MIDDLEWARE, env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
SIMPLE_JWT["SIGNING_KEY"] = env("JWT_SIGNING_KEY", default=SECRET_KEY)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
REGISTRATION_OPEN = env.bool("REGISTRATION_OPEN", default=False)

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
REFRESH_COOKIE["secure"] = True

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="LifeOS <noreply@localhost>")

# Collected static files (Django admin) are served by the app itself; nginx only proxies /api.
MIDDLEWARE = [
    *MIDDLEWARE[:2],  # RequestIdMiddleware, SecurityMiddleware
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[2:],
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
