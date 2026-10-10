from django.contrib import admin
from django.forms.widgets import Script
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

    class Media:
        js = (Script("media_library/image_preview.js", type="module"),)

    @admin.display(description="Предпросмотр")
    def preview(self, obj):
        if not obj or not obj.file:
            return "—"
        return format_html(
            '<a href="{}" class="media-image-preview" data-caption="{}" '
            'aria-label="Открыть изображение: {}" aria-haspopup="dialog" '
            'style="display:inline-block;cursor:zoom-in">'
            '<img src="{}" alt="{}" style="max-width:160px;max-height:100px"></a>',
            obj.file.url,
            obj.title,
            obj.title,
            obj.file.url,
            obj.alt_text,
        )

    def has_delete_permission(self, request, obj=None):
        # Articles contain file URLs; keep their images until usage tracking exists.
        return False
