from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_safe

from site_settings.formats import DOCUMENT_FORMATS
from site_settings.models import SiteSettings

from .forms import DocumentForm
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


@require_safe
def view(request, pk):
    document = get_object_or_404(Document, pk=pk, file_format="PDF")
    try:
        file = document.file.open("rb")
    except OSError as exc:
        raise Http404 from exc
    response = FileResponse(
        file,
        as_attachment=False,
        filename=document.original_name,
        content_type="application/pdf",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


def require_editor(request, permission):
    if not request.user.has_perm(f"document_library.{permission}_document") or not any(
        request.user.has_perm(f"{app}.{action}_{model}")
        for app, model in (
            ("articles", "article"),
            ("article_collections", "collection"),
        )
        for action in ("add", "change")
    ):
        raise PermissionDenied


def document_data(document):
    return {
        "id": document.pk,
        "title": document.title,
        "filename": document.original_name,
        "format": document.file_format,
        "url": document.get_link_url(),
    }


@require_GET
def library(request):
    require_editor(request, "view")
    settings = SiteSettings.load()
    formats = [
        name
        for name, (field, _) in DOCUMENT_FORMATS.items()
        if getattr(settings, field)
    ]
    documents = Document.objects.filter(file_format__in=formats)
    query = request.GET.get("q", "").strip()[:200]
    if query:
        documents = documents.filter(
            Q(title__icontains=query) | Q(original_name__icontains=query)
        )
    page = Paginator(documents, 20).get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "documents": [document_data(doc) for doc in page],
            "page": page.number,
            "pages": page.paginator.num_pages,
        }
    )


@require_POST
def upload(request):
    require_editor(request, "add")
    form = DocumentForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse(
            {
                "error": {
                    "message": " ".join(
                        str(message)
                        for errors in form.errors.values()
                        for message in errors
                    )
                }
            },
            status=400,
        )
    return JsonResponse(document_data(form.save()), status=201)
