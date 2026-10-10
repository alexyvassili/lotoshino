from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from .html import clean_article_html
from .models import Article


@require_safe
def detail(request, slug):
    article = get_object_or_404(Article, slug=slug)
    return render(
        request,
        "articles/detail.html",
        {"article": article, "article_content": clean_article_html(article.content)},
    )
