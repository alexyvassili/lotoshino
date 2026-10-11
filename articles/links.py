from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

from django.urls import Resolver404, resolve

from .models import Article


class ArticleLinks(HTMLParser):
    def __init__(self, page_url):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.netloc = urlsplit(page_url).netloc.lower()
        self.slugs = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        try:
            url = urlsplit(urljoin(self.page_url, href.strip()))
            if url.scheme not in {"http", "https"} or url.netloc.lower() != self.netloc:
                return
            # Also recognize URLs which CommonMiddleware redirects to a trailing slash.
            match = resolve(unquote(url.path).rstrip("/") + "/")
        except ValueError, Resolver404:
            return
        if match.view_name == "articles:detail":
            self.slugs.add(match.kwargs["slug"])


def linked_article_slugs(content, page_url):
    parser = ArticleLinks(page_url)
    parser.feed(content)
    return parser.slugs


def unpublished_link_targets(article, site_url):
    slugs = linked_article_slugs(
        article.content, urljoin(site_url, article.get_absolute_url())
    )
    return Article.objects.filter(is_published=False, slug__in=slugs).order_by(
        "title", "pk"
    )


def published_link_sources(article, site_url, previous_slug):
    targets = {article.slug, previous_slug}
    sources = []
    for source in (
        Article.objects.filter(is_published=True)
        .exclude(pk=article.pk)
        .only("pk", "title", "slug", "content")
        .order_by("title", "pk")
        .iterator()
    ):
        if targets & linked_article_slugs(
            source.content, urljoin(site_url, source.get_absolute_url())
        ):
            sources.append(source)
    return sources
