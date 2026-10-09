from django.core.exceptions import ImproperlyConfigured

from .base import *

if not SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY for production.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS for production.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "lotoshino"),
        "USER": os.environ.get("POSTGRES_USER", "lotoshino"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
    }
}

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
