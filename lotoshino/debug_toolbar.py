from django.conf import settings


def show_toolbar(request):
    """Protect both the toolbar and its data endpoints."""
    return (
        settings.DEBUG
        and request.META.get("REMOTE_ADDR") in settings.INTERNAL_IPS
        and request.user.is_authenticated
        and request.user.is_active
        and request.user.is_superuser
    )
