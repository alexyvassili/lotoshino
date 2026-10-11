from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from media_library.downloads import image_download_urls

from .html import clean_article_html
from .models import Article


@require_safe
def detail(request, slug):
    article = get_object_or_404(Article, slug=slug, is_published=True)
    content = clean_article_html(article.content)
    return render(
        request,
        "articles/detail.html",
        {
            "article": article,
            "article_content": content,
            "image_downloads": image_download_urls(content),
            "image_base": settings.MEDIA_URL.rstrip("/") + "/images/",
        },
    )
