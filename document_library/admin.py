from django.contrib import admin
from django.template.defaultfilters import filesizeformat
from django.urls import path
from django.utils.html import format_html

from .forms import DocumentForm
from .models import Document
from .views import library, upload


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    def get_urls(self):
        return [
            path(
                "editor/library/",
                self.admin_site.admin_view(library),
                name="document_editor_library",
            ),
            path(
                "editor/upload/",
                self.admin_site.admin_view(upload),
                name="document_editor_upload",
            ),
            *super().get_urls(),
        ]

    form = DocumentForm
    fields = (
        "title",
        "file",
        "original_name",
        "file_format",
        "file_size",
        "download",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "original_name",
        "file_format",
        "file_size",
        "download",
        "created_at",
        "updated_at",
    )
    list_display = ("title", "file_format", "file_size", "download", "updated_at")
    list_filter = ("file_format",)
    search_fields = ("title", "original_name")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "file") if obj is not None else fields

    @admin.display(description="Размер файла")
    def file_size(self, obj):
        if not obj or not obj.file:
            return "—"
        try:
            return filesizeformat(obj.file.size)
        except OSError:
            return "Файл недоступен"

    @admin.display(description="Ссылка на документ")
    def download(self, obj):
        if not obj or not obj.pk:
            return "—"
        return format_html('<a href="{}">Скачать документ</a>', obj.get_absolute_url())

    def has_delete_permission(self, request, obj=None):
        return False
