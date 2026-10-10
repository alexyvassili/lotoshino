from typing import ClassVar

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.forms.widgets import Script
from django.http import HttpResponseRedirect
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .forms import ImageForm
from .models import Image, ImageSettings

RESIZE_DESCRIPTION = (
    "Изображение уменьшается до заданной ширины, сохраняя пропорции. "
    "Высота рассчитывается автоматически и ограничивается указанным максимумом."
)


@admin.register(ImageSettings)
class ImageSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Максимальный размер изображения",
            {
                "description": "При загрузке большие изображения уменьшаются до этих границ. "
                "Пропорции сохраняются, маленькие изображения не увеличиваются.",
                "fields": ("max_image_width", "max_image_height"),
            },
        ),
        (
            "Галерея — горизонтальные изображения",
            {
                "description": RESIZE_DESCRIPTION,
                "fields": (
                    "gallery_preview_width",
                    "gallery_preview_height",
                    "gallery_full_width",
                    "gallery_full_height",
                ),
            },
        ),
        (
            "Галерея — вертикальные изображения",
            {
                "description": RESIZE_DESCRIPTION,
                "fields": (
                    "gallery_portrait_preview_width",
                    "gallery_portrait_preview_height",
                    "gallery_portrait_full_width",
                    "gallery_portrait_full_height",
                ),
            },
        ),
        (
            "Статьи — горизонтальные изображения",
            {
                "description": RESIZE_DESCRIPTION,
                "fields": (
                    "article_preview_width",
                    "article_preview_height",
                    "article_full_width",
                    "article_full_height",
                ),
            },
        ),
        (
            "Статьи — вертикальные изображения",
            {
                "description": RESIZE_DESCRIPTION,
                "fields": (
                    "article_portrait_preview_width",
                    "article_portrait_preview_height",
                    "article_portrait_full_width",
                    "article_portrait_full_height",
                ),
            },
        ),
    )

    class Media:
        css: ClassVar = {"all": ("media_library/image_settings.css",)}

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        settings = ImageSettings.load()
        return HttpResponseRedirect(
            reverse("admin:media_library_imagesettings_change", args=[settings.pk])
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    form = ImageForm
    fields = (
        "title",
        "file",
        "alt_text",
        "preview",
        "available_sizes",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("preview", "available_sizes", "created_at", "updated_at")
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

    @admin.display(description="Имеющиеся размеры")
    def available_sizes(self, obj):
        if not obj or not obj.pk:
            return "Размеры появятся после загрузки изображения."
        versions = [("Основная версия", obj.file, obj.file.width, obj.file.height, "—")]
        for rendition in obj.renditions.order_by("kind", "-created_at"):
            title = rendition.get_kind_display()
            if rendition.source_name != obj.file.name:
                title += " (предыдущий исходник)"
            versions.append(
                (
                    title,
                    rendition.file,
                    rendition.width,
                    rendition.height,
                    f"{rendition.max_width} × {rendition.max_height} px",  # noqa: RUF001
                )
            )
        rows = []
        for title, file, width, height, bounds in versions:
            try:
                file_size = filesizeformat(file.size)
            except OSError:
                file_size = "Файл недоступен"
            rows.append((title, width, height, bounds, file_size, file.url, title))
        return format_html(
            "<table><thead><tr><th>Версия</th><th>Размер</th><th>Ограничение</th>"
            "<th>Объём файла</th><th></th></tr></thead><tbody>{}</tbody></table>",
            format_html_join(
                "",
                "<tr><td>{}</td><td>{} &times; {} px</td><td>{}</td><td>{}</td>"
                '<td><a href="{}" class="media-image-preview" data-caption="{}" '
                'aria-haspopup="dialog">Открыть</a></td></tr>',
                rows,
            ),
        )
