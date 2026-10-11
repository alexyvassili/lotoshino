from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

from django.urls import Resolver404, resolve, reverse

from article_collections.models import Collection

from .models import Article


class ArticleLinks(HTMLParser):
    def __init__(self, page_url):
        super().__init__(convert_charrefs=True)
        self.page_url = page_url
        self.netloc = urlsplit(page_url).netloc.lower()
        self.slugs = set()
        self.pages = {}
        self.collection_slugs = set()

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
            slug = match.kwargs["slug"]
            self.slugs.add(slug)
            self.pages.setdefault(
                reverse("articles:detail", kwargs={"slug": slug}), slug
            )
        elif match.view_name == "article_collection":
            slug = match.kwargs["slug"]
            self.collection_slugs.add(slug)
            self.pages.setdefault(
                reverse("article_collection", kwargs={"slug": slug}),
                ("collection", slug),
            )
        elif match.view_name == "index":
            self.pages.setdefault(reverse("index"), None)


def linked_article_slugs(content, page_url):
    parser = ArticleLinks(page_url)
    parser.feed(content)
    return parser.slugs


def linked_site_pages(article, site_url):
    parser = ArticleLinks(urljoin(site_url, article.get_absolute_url()))
    parser.feed(article.content)
    articles = {
        target.slug: target
        for target in Article.objects.filter(slug__in=parser.slugs).only(
            "slug", "title", "is_published"
        )
    }
    collections = {
        target.slug: target
        for target in Collection.objects.filter(slug__in=parser.collection_slugs)
    }
    pages = []
    for url, slug in parser.pages.items():
        if slug is None:
            pages.append((url, "Главная страница", ""))
        elif isinstance(slug, tuple):
            target = collections.get(slug[1])
            if target:
                pages.append(
                    (
                        url,
                        target.title,
                        "" if target.is_published else " — не опубликовано",
                    )
                )
            else:
                pages.append((url, url, " — страница не найдена"))
        elif target := articles.get(slug):
            status = "" if target.is_published else " — не опубликовано"
            pages.append((url, target.title, status))
        else:
            pages.append((url, url, " — страница не найдена"))
    return pages


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
