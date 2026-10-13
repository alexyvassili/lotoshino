from pathlib import Path

from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST, require_safe
from PIL import Image as PillowImage

from articles.models import Article
from media_library.forms import ImageForm
from media_library.models import Image
from media_library.renditions import article_image_data
from media_library.views import prepared_image_response

from .images import article_images, picker_image
from .models import Collection


def require_collection_editor(user):
    if not (
        user.has_perm("article_collections.add_collection")
        or user.has_perm("article_collections.change_collection")
    ):
        raise PermissionDenied


@require_GET
@permission_required("media_library.view_image", raise_exception=True)
def image_picker(request):
    require_collection_editor(request.user)
    images = Image.objects.all()
    if request.GET.get("scope") == "article":
        if not request.user.has_perm("articles.view_article"):
            raise PermissionDenied
        article_id = request.GET.get("article", "")
        if not article_id.isdecimal():
            return JsonResponse({"images": [], "page": 1, "pages": 1})
        images = article_images(get_object_or_404(Article, pk=article_id))
    query = request.GET.get("q", "").strip()[:200]
    if query:
        images = images.filter(Q(title__icontains=query) | Q(alt_text__icontains=query))
    page = Paginator(images, 24).get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "images": [picker_image(image) for image in page],
            "page": page.number,
            "pages": page.paginator.num_pages,
        }
    )


@require_POST
@permission_required("media_library.add_image", raise_exception=True)
def upload_image(request):
    require_collection_editor(request.user)
    upload = request.FILES.get("upload")
    if upload is None:
        return JsonResponse({"error": {"message": "Выберите изображение."}}, status=400)
    form = ImageForm(
        data={"title": Path(upload.name).stem[:255], "alt_text": ""},
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
    return prepared_image_response(image, status=201)


@require_POST
@permission_required("media_library.view_image", raise_exception=True)
def prepare_image(request, pk):
    require_collection_editor(request.user)
    return prepared_image_response(get_object_or_404(Image, pk=pk))


@require_safe
def detail(request, slug):
    collection = get_object_or_404(Collection, slug=slug, is_published=True)
    items = list(
        collection.items.filter(article__is_published=True).select_related(
            "article", "image"
        )
    )
    previews = {}
    for item in items:
        item.preview = None
        if item.image_id:
            if item.image_id not in previews:
                try:
                    previews[item.image_id] = article_image_data(item.image)
                except OSError, ValueError, PillowImage.DecompressionBombError:
                    previews[item.image_id] = None
            item.preview = previews[item.image_id]
    return render(
        request,
        collection.template_name,
        {"collection": collection, "items": items},
    )
