from typing import ClassVar

from django.contrib import admin
from django.urls import path
from django.utils.html import format_html

from . import views
from .forms import CollectionForm, CollectionItemForm
from .models import Collection, CollectionItem


class CollectionItemInline(admin.StackedInline):
    model = CollectionItem
    verbose_name = "Статья подборки"
    verbose_name_plural = "Статьи подборки"
    form = CollectionItemForm
    autocomplete_fields = ("article",)
    fields = (
        "article",
        "publication_status",
        "title",
        "image",
        "image_caption",
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
    form = CollectionForm
    fields = (
        "title",
        "slug",
        "template_name",
        "introduction",
        "closing_text",
        "is_published",
    )
    list_display = ("title", "slug", "template_display", "is_published", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("title", "slug", "introduction")
    inlines = (CollectionItemInline,)

    def get_fields(self, request, obj=None):
        return tuple(
            "template_display" if obj and field == "template_name" else field
            for field in self.fields
        )

    def get_readonly_fields(self, request, obj=None):
        return ("template_display",) if obj else ()

    @admin.display(description="Шаблон")
    def template_display(self, obj):
        return format_html(
            "{}<br><code>{}</code>", obj.get_template_name_display(), obj.template_name
        )

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
