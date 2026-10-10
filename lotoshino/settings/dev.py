from .base import *

DEBUG = True
# Read templates on each request: Uvicorn's reload watches Python files only.
TEMPLATES[0]["APP_DIRS"] = False
TEMPLATES[0]["OPTIONS"]["loaders"] = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]"]
SECRET_KEY = (
    SECRET_KEY or "django-insecure-f4@q)j&za1iad7sjuyc-vzno*2!&d%!0#r_mv)kw+1*v+cy@h("
)
