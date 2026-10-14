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
from .usage import attach_image_pages

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
        "used_on_pages",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "preview",
        "available_sizes",
        "used_on_pages",
        "created_at",
        "updated_at",
    )
    list_display = ("title", "preview", "used_on_pages", "updated_at")
    search_fields = ("title", "alt_text")

    class Media:
        js = (
            Script("media_library/image_preview.js?v=2", type="module"),
            "media_library/copy_image_url.js",
        )
        css: ClassVar = {"all": ("media_library/copy_image_url.css",)}

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        return tuple(
            "file_link" if field == "file" and obj else field for field in fields
        )

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return (*fields, "file", "file_link") if obj is not None else fields

    @admin.display(description="Изображение")
    def file_link(self, obj):
        return format_html(
            '<span class="image-file-link"><a href="{}">{}</a>'
            '<button type="button" class="copy-image-url" data-copy-url="{}" '
            'title="Копировать относительный адрес" aria-label="Копировать относительный адрес">'
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.7" aria-hidden="true"><rect x="8" y="8" width="12" height="13" rx="2"/>'
            '<path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></svg></button>'
            '<span class="copy-image-status" role="status" aria-live="polite"></span></span>',
            obj.file.url,
            obj.file.name,
            obj.file.url,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("renditions")

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context)
        context = getattr(response, "context_data", None)
        if context and "cl" in context:
            attach_image_pages(context["cl"].result_list)
        return response

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj is not None:
            attach_image_pages([obj])
        return obj

    @admin.display(description="Используется на страницах")
    def used_on_pages(self, obj):
        pages = getattr(obj, "used_pages", ())
        if not pages:
            return "Нет использований."
        return format_html(
            "<ul>{}</ul>",
            format_html_join(
                "",
                '<li><a href="{}" target="_blank" rel="noopener noreferrer">{}</a></li>',
                pages,
            ),
        )

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
            rows.append(
                (title, width, height, bounds, file_size, file.url, title, obj.file.url)
            )
        return format_html(
            "<table><thead><tr><th>Версия</th><th>Размер</th><th>Ограничение</th>"
            "<th>Объём файла</th><th></th></tr></thead><tbody>{}</tbody></table>",
            format_html_join(
                "",
                "<tr><td>{}</td><td>{} &times; {} px</td><td>{}</td><td>{}</td>"
                '<td><a href="{}" class="media-image-preview" data-caption="{}" '
                'data-download-url="{}" '
                'aria-haspopup="dialog">Открыть</a></td></tr>',
                rows,
            ),
        )
