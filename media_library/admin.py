from django.contrib import admin
from django.utils.html import format_html

from .forms import ImageForm
from .models import Image


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    form = ImageForm
    fields = ("title", "file", "alt_text", "preview", "created_at", "updated_at")
    readonly_fields = ("preview", "created_at", "updated_at")
    list_display = ("title", "preview", "updated_at")
    search_fields = ("title", "alt_text")

    @admin.display(description="Предпросмотр")
    def preview(self, obj):
        if not obj or not obj.file:
            return "—"
        return format_html(
            '<img src="{}" alt="{}" style="max-width:160px;max-height:100px">',
            obj.file.url,
            obj.alt_text,
        )

    def has_delete_permission(self, request, obj=None):
        # Articles contain file URLs; keep their images until usage tracking exists.
        return False
