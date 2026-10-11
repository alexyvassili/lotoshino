from django.conf import settings
from django.db.models import Q

from .models import Image
from .usage import ImageSources


def image_download_urls(content):
    """Resolve article image URLs to their stored masters without reading files."""
    sources = ImageSources()
    sources.feed(content)
    prefix = settings.MEDIA_URL.rstrip("/") + "/"
    names = {url[len(prefix) :] for url in sources.urls if url.startswith(prefix)}
    if not names:
        return {}
    images = (
        Image.objects.filter(Q(file__in=names) | Q(renditions__file__in=names))
        .distinct()
        .prefetch_related("renditions")
    )
    downloads = {}
    for image in images:
        if image.file.url in sources.urls:
            downloads[image.file.url] = image.file.url
        for rendition in image.renditions.all():
            if rendition.file.url in sources.urls:
                downloads[rendition.file.url] = rendition.file.storage.url(
                    rendition.source_name
                )
    return downloads
