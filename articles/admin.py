from django.contrib import admin
from django.urls import path

from media_library.views import image_library, prepare_article_image, upload_image

from .forms import ArticleForm
from .models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleForm
    fields = ("title", "slug", "content", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    list_display = ("title", "slug", "created_at", "updated_at")
    search_fields = ("title", "slug", "content")

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
