from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
async def index(request):
    return HttpResponse("Лотошино", content_type="text/plain; charset=utf-8")
