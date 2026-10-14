from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils.http import http_date
from django.views.decorators.http import require_safe
from django.views.static import was_modified_since

from .storage import IMAGE_FILENAME, image_storage


@require_safe
def image_file(request, filename):
    """Resolve the UUID prefix without a database query or a redirect."""
    if not IMAGE_FILENAME.fullmatch(filename):
        raise Http404
    name = f"images/{filename}"
    try:
        modified = image_storage.get_modified_time(name).timestamp()
        if not was_modified_since(request.headers.get("If-Modified-Since"), modified):
            response = HttpResponseNotModified()
        else:
            response = FileResponse(image_storage.open(name, "rb"), filename=filename)
    except FileNotFoundError:
        raise Http404 from None
    response["Last-Modified"] = http_date(modified)
    response["X-Content-Type-Options"] = "nosniff"
    return response
