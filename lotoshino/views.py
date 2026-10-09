from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe


@require_safe
async def index(request):
    return TemplateResponse(request, "home/home_page.html")
