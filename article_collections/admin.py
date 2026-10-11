from typing import ClassVar

from django.contrib import admin
from django.urls import path

from . import views
from .forms import CollectionItemForm
from .models import Collection, CollectionItem


class CollectionItemInline(admin.StackedInline):
    model = CollectionItem
    form = CollectionItemForm
    autocomplete_fields = ("article",)
    fields = (
        "article",
        "publication_status",
        "title",
        "image",
        "annotation",
        "link_text",
        "position",
    )
    readonly_fields = ("publication_status",)
    extra = 0

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "image" and field:
            # The picker handles selection and upload without a second popup.
            field.widget = CollectionItemForm.base_fields["image"].widget
        if db_field.name == "article" and field:
            field.widget.can_delete_related = False
        return field

    @admin.display(description="Статус статьи")
    def publication_status(self, obj):
        if obj and obj.article_id:
            return (
                "Опубликовано"
                if obj.article.is_published
                else "Черновик — скрыто на странице подборки"
            )
        return "—"


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    fields = ("title", "slug", "introduction", "is_published")
    list_display = ("title", "slug", "is_published", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("title", "slug", "introduction")
    inlines = (CollectionItemInline,)

    class Media:
        css: ClassVar = {
            "all": ("article_collections/admin.css", "article_collections/items.css")
        }
        js = ("article_collections/admin.js",)

    def get_urls(self):
        return [
            path(
                "images/",
                self.admin_site.admin_view(views.image_picker),
                name="collection_image_picker",
            ),
            path(
                "images/upload/",
                self.admin_site.admin_view(views.upload_image),
                name="collection_image_upload",
            ),
            path(
                "images/<int:pk>/prepare/",
                self.admin_site.admin_view(views.prepare_image),
                name="collection_image_prepare",
            ),
            *super().get_urls(),
        ]
