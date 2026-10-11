from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {"fields": ("max_upload_size_mb",)}),
        (
            "Разрешённые форматы изображений",
            {
                "description": "Галочки разрешают новые загрузки. Уже загруженные изображения сохраняются.",
                "fields": ("allow_image_jpeg", "allow_image_png", "allow_image_webp"),
            },
        ),
        (
            "Разрешённые форматы файлов",
            {
                "description": "Для каждого документа проверяются расширение и содержимое файла.",
                "fields": (
                    "allow_file_doc",
                    "allow_file_docx",
                    "allow_file_odt",
                    "allow_file_pdf",
                    "allow_file_rtf",
                ),
            },
        ),
    )

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        settings = SiteSettings.load()
        return HttpResponseRedirect(
            reverse("admin:site_settings_sitesettings_change", args=[settings.pk])
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
