"""
ASGI config for lotoshino project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lotoshino.settings.dev")

application = get_asgi_application()

# Uvicorn needs an explicit development-only handler for static files.
if settings.DEBUG:
    application = ASGIStaticFilesHandler(application)
