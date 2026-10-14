from collections import defaultdict
from html.parser import HTMLParser

from article_collections.models import Collection, CollectionItem
from articles.html import clean_article_html
from articles.illustrations import is_local_illustration_url
from articles.models import Article


class ImageSources(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            src = attrs.get("src")
            if src:
                self.urls.add(src)
        elif tag == "a" and attrs.get("data-illustration") == "true":
            href = attrs.get("href")
            if is_local_illustration_url(href):
                self.urls.add(href)


def attach_image_pages(images):
    """Read article content once per admin page, including historical renditions."""
    images_by_url = defaultdict(list)
    images_by_id = {}
    for image in images:
        image.used_pages = []
        images_by_id[image.pk] = image
        urls = {image.file.url}
        for rendition in image.renditions.all():
            urls.add(rendition.file.url)
            # An older article may still reference the master replaced later.
            urls.add(image.file.storage.url(rendition.source_name))
        for url in urls:
            images_by_url[url].append(image.pk)
    if not images_by_id:
        return

    for article in (
        Article.objects.only("pk", "title", "slug", "content")
        .order_by("title", "pk")
        .iterator()
    ):
        sources = ImageSources()
        sources.feed(clean_article_html(article.content))
        used_ids = {pk for url in sources.urls for pk in images_by_url.get(url, ())}
        for pk in used_ids:
            images_by_id[pk].used_pages.append(
                (article.get_absolute_url(), article.title)
            )

    seen = set()
    for collection in Collection.objects.only(
        "pk", "title", "slug", "introduction", "closing_text"
    ).order_by("title", "pk"):
        sources = ImageSources()
        sources.feed(
            clean_article_html(collection.introduction + collection.closing_text)
        )
        used_ids = {pk for url in sources.urls for pk in images_by_url.get(url, ())}
        for pk in used_ids:
            seen.add((pk, collection.pk))
            images_by_id[pk].used_pages.append(
                (collection.get_absolute_url(), collection.title)
            )
    for item in (
        CollectionItem.objects.filter(image_id__in=images_by_id)
        .select_related("collection")
        .order_by("collection__title", "collection_id")
    ):
        key = (item.image_id, item.collection_id)
        if key not in seen:
            seen.add(key)
            images_by_id[item.image_id].used_pages.append(
                (item.collection.get_absolute_url(), item.collection.title)
            )
