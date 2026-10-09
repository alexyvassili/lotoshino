from django.contrib import admin

from .models import HomePage


@admin.register(HomePage)
class HomePageAdmin(admin.ModelAdmin):
    fields = (
        "title",
        "content",
        "seo_title",
        "seo_description",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("created_at", "updated_at")
    list_display = ("title", "updated_at")

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not HomePage.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
