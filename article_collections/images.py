from html.parser import HTMLParser

from django.conf import settings
from django.db.models import Q

from media_library.models import Image


class EmbeddedImages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sources = set()

    def handle_starttag(self, tag, attrs):
        if tag == "img":
            src = dict(attrs).get("src")
            if src:
                self.sources.add(src)


def article_images(article):
    parser = EmbeddedImages()
    parser.feed(article.content)
    prefix = settings.MEDIA_URL.rstrip("/") + "/"
    names = {url[len(prefix) :] for url in parser.sources if url.startswith(prefix)}
    return Image.objects.filter(
        Q(file__in=names)
        | Q(renditions__file__in=names)
        | Q(renditions__source_name__in=names)
    ).distinct()


def picker_image(image):
    preview = (
        image.renditions.filter(kind="article_preview", source_name=image.file.name)
        .order_by("-created_at")
        .first()
    )
    return {
        "id": image.pk,
        "title": image.title,
        "url": preview.file.url if preview else image.file.url,
    }
