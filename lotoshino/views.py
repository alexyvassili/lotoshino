from pathlib import Path

from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe


@require_safe
async def index(request):
    return TemplateResponse(request, "home/home_page.html")


@require_safe
def favicon(request):
    icon = Path(__file__).parent / "static" / "favicon.ico"
    return HttpResponse(icon.read_bytes(), content_type="image/vnd.microsoft.icon")
