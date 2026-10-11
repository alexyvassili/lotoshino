from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from media_library.views import image_library, prepare_article_image, upload_image

from .forms import ArticleForm
from .links import published_link_sources, unpublished_link_targets
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleForm
    fields = ("title", "slug", "is_published", "content", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    list_display = ("title", "slug", "is_published", "created_at", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("title", "slug", "content")

    def save_model(self, request, obj, form, change):
        unpublishing = (
            change and "is_published" in form.changed_data and not obj.is_published
        )
        previous_slug = (
            Article.objects.values_list("slug", flat=True).get(pk=obj.pk)
            if unpublishing
            else obj.slug
        )
        super().save_model(request, obj, form, change)
        site_url = request.build_absolute_uri("/")
        if obj.is_published:
            self.warn_about_links(
                request,
                unpublished_link_targets(obj, site_url),
                "Сохранённая статья содержит ссылки на неопубликованные статьи:",
            )
        elif unpublishing:
            self.warn_about_links(
                request,
                published_link_sources(obj, site_url, previous_slug),
                "Статья снята с публикации. На неё ссылаются опубликованные статьи:",  # noqa: RUF001
            )

    def warn_about_links(self, request, articles, description):
        links = format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            (
                (
                    reverse("admin:articles_article_change", args=[article.pk]),
                    article.title,
                )
                for article in articles
            ),
        )
        if links:
            self.message_user(
                request,
                format_html(
                    "{} {}. Посетители при переходе по этим ссылкам увидят страницу 404.",
                    description,
                    links,
                ),
                level=messages.WARNING,
            )

    def get_urls(self):
        return [
            path(
                "images/<int:image_id>/prepare/",
                self.admin_site.admin_view(prepare_article_image),
                name="article_image_prepare",
            ),
            path(
                "images/upload/",
                self.admin_site.admin_view(upload_image),
                name="article_image_upload",
            ),
            path(
                "images/library/",
                self.admin_site.admin_view(image_library),
                name="article_image_library",
            ),
            *super().get_urls(),
        ]
