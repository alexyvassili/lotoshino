from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .forms import ImageForm
from .models import Image


def can_edit_articles(user):
    return user.has_perm("articles.add_article") or user.has_perm(
        "articles.change_article"
    )


@require_POST
def upload_image(request):
    if not can_edit_articles(request.user) or not request.user.has_perm(
        "media_library.add_image"
    ):
        raise PermissionDenied
    upload = request.FILES.get("upload")
    if upload is None:
        return JsonResponse({"error": {"message": "Выберите изображение."}}, status=400)
    form = ImageForm(
        data={"title": Path(upload.name).stem[:255] or "Изображение", "alt_text": ""},
        files={"file": upload},
    )
    if not form.is_valid():
        return JsonResponse(
            {
                "error": {
                    "message": " ".join(
                        str(error)
                        for errors in form.errors.values()
                        for error in errors
                    )
                }
            },
            status=400,
        )
    image = form.save()
    return JsonResponse({"url": image.file.url}, status=201)


@require_GET
def image_library(request):
    if not can_edit_articles(request.user) or not request.user.has_perm(
        "media_library.view_image"
    ):
        raise PermissionDenied
    images = Image.objects.all()
    query = request.GET.get("q", "").strip()[:200]
    if query:
        images = images.filter(Q(title__icontains=query) | Q(alt_text__icontains=query))
    page = Paginator(images, 24).get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "images": [
                {
                    "id": image.pk,
                    "title": image.title,
                    "alt": image.alt_text,
                    "url": image.file.url,
                }
                for image in page
            ],
            "page": page.number,
            "pages": page.paginator.num_pages,
        }
    )
