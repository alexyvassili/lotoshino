from django.contrib import admin

from .models import (
    DrupalMigrateArticleMap,
    DrupalMigrateArticles,
    DrupalMigrateCollectionMap,
    DrupalMigrateFileManaged,
    DrupalMigrateFileMap,
    DrupalMigrateFileUsage,
    DrupalMigrateURL,
)


class MigrationSnapshotAdmin(admin.ModelAdmin):
    """Source snapshots are written by the importer, not edited alongside articles."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DrupalMigrateArticles)
class ArticleSourceAdmin(MigrationSnapshotAdmin):
    list_display = (
        "drupal_migrate_node_id",
        "drupal_migrate_title",
        "drupal_migrate_status",
    )
    search_fields = ("drupal_migrate_title", "=drupal_migrate_node_id")


@admin.register(DrupalMigrateFileManaged)
class FileSourceAdmin(MigrationSnapshotAdmin):
    list_display = (
        "drupal_migrate_filename",
        "drupal_migrate_file_id",
        "drupal_migrate_filesize",
    )
    search_fields = ("drupal_migrate_filename", "=drupal_migrate_file_id")


@admin.register(DrupalMigrateURL)
class OldURLAdmin(MigrationSnapshotAdmin):
    list_display = ("url", "drupal_article", "drupal_file")
    search_fields = ("url",)
    list_select_related = ("drupal_article", "drupal_file")


for model in (
    DrupalMigrateArticleMap,
    DrupalMigrateCollectionMap,
    DrupalMigrateFileMap,
    DrupalMigrateFileUsage,
):
    admin.site.register(model, MigrationSnapshotAdmin)
