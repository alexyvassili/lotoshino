from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe

from .models import Document


@require_safe
def download(request, pk):
    document = get_object_or_404(Document, pk=pk)
    try:
        file = document.file.open("rb")
    except OSError as exc:
        raise Http404 from exc
    response = FileResponse(file, as_attachment=True, filename=document.original_name)
    response["X-Content-Type-Options"] = "nosniff"
    return response
