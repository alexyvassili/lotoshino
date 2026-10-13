from typing import ClassVar

from django.contrib import admin

from .forms import MenuItemForm
from .models import Menu, MenuItem


class MenuItemInline(admin.StackedInline):
    model = MenuItem
    form = MenuItemForm
    fields = ("title", "page", "url", "is_visible", "position")
    extra = 0


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    fields = ("name",)
    readonly_fields = ("name",)
    inlines = (MenuItemInline,)
    actions = None

    @admin.display(description="Меню")
    def name(self, obj):
        return str(obj)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    class Media:
        css: ClassVar = {"all": ("navigation/admin.css",)}
        js = ("navigation/admin.js",)
