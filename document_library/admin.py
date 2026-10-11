from django.contrib import admin
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html

from .forms import DocumentForm
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
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
