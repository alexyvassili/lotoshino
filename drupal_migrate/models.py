from django.core.exceptions import ValidationError
from django.db import models


class DrupalMigrateArticles(models.Model):
    drupal_migrate_node_id = models.PositiveIntegerField("ID Drupal (nid)", unique=True)
    drupal_migrate_title = models.CharField("Заголовок Drupal", max_length=255)
    drupal_migrate_status = models.BooleanField("Опубликовано в Drupal")
    drupal_migrate_created = models.PositiveBigIntegerField("Создано в Drupal (Unix)")
    drupal_migrate_changed = models.PositiveBigIntegerField("Изменено в Drupal (Unix)")

    class Meta:
        verbose_name = "Исходная страница Drupal"
        verbose_name_plural = "Исходные страницы Drupal"

    def __str__(self):
        return f"{self.drupal_migrate_node_id}: {self.drupal_migrate_title}"


class DrupalMigrateArticleMap(models.Model):
    drupal_article = models.OneToOneField(
        DrupalMigrateArticles, on_delete=models.PROTECT, related_name="article_map"
    )
    article = models.OneToOneField("articles.Article", on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Соответствие статьи"
        verbose_name_plural = "Соответствия статей"

    def __str__(self):
        return f"{self.drupal_article} → {self.article}"


class DrupalMigrateCollectionMap(models.Model):
    drupal_article = models.OneToOneField(
        DrupalMigrateArticles, on_delete=models.PROTECT, related_name="collection_map"
    )
    collection = models.OneToOneField(
        "article_collections.Collection", on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = "Соответствие подборки"
        verbose_name_plural = "Соответствия подборок"

    def __str__(self):
        return f"{self.drupal_article} → {self.collection}"


class DrupalMigrateFileManaged(models.Model):
    drupal_migrate_file_id = models.PositiveIntegerField(
        "ID Drupal (fid)", unique=True, null=True, blank=True
    )
    drupal_migrate_filename = models.CharField("Имя файла Drupal", max_length=255)
    drupal_migrate_timestamp = models.PositiveBigIntegerField(
        "Дата Drupal (Unix)", null=True, blank=True
    )
    drupal_migrate_filemime = models.CharField("MIME Drupal", max_length=255)
    drupal_migrate_filesize = models.PositiveBigIntegerField("Исходный размер, байт")
    drupal_migrate_width = models.PositiveIntegerField(
        "Исходная ширина", null=True, blank=True
    )
    drupal_migrate_height = models.PositiveIntegerField(
        "Исходная высота", null=True, blank=True
    )

    class Meta:
        verbose_name = "Исходный файл Drupal"
        verbose_name_plural = "Исходные файлы Drupal"

    def __str__(self):
        return self.drupal_migrate_filename


class DrupalMigrateFileMap(models.Model):
    drupal_file = models.OneToOneField(
        DrupalMigrateFileManaged, on_delete=models.PROTECT, related_name="file_map"
    )
    image = models.ForeignKey(
        "media_library.Image", on_delete=models.PROTECT, null=True, blank=True
    )
    document = models.ForeignKey(
        "document_library.Document", on_delete=models.PROTECT, null=True, blank=True
    )
    rendition = models.ForeignKey(
        "media_library.ImageRendition", on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        verbose_name = "Соответствие файла"
        verbose_name_plural = "Соответствия файлов"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        image__isnull=False,
                        document__isnull=True,
                        rendition__isnull=True,
                    )
                    | models.Q(
                        image__isnull=True,
                        document__isnull=False,
                        rendition__isnull=True,
                    )
                    | models.Q(
                        image__isnull=True,
                        document__isnull=True,
                        rendition__isnull=False,
                    )
                ),
                name="drupal_file_exactly_one_target",
            )
        ]

    def __str__(self):
        return f"{self.drupal_file} → {self.image or self.document or self.rendition}"


class DrupalMigrateFileUsage(models.Model):
    drupal_article = models.ForeignKey(DrupalMigrateArticles, on_delete=models.PROTECT)
    drupal_file = models.ForeignKey(DrupalMigrateFileManaged, on_delete=models.PROTECT)
    drupal_migrate_field = models.CharField("Поле или вид вставки", max_length=100)
    drupal_migrate_position = models.PositiveIntegerField("Порядок вставки")
    drupal_migrate_alt = models.TextField("Исходный alt", blank=True)
    drupal_migrate_title = models.TextField("Исходный title", blank=True)
    drupal_migrate_width = models.PositiveIntegerField(null=True, blank=True)
    drupal_migrate_height = models.PositiveIntegerField(null=True, blank=True)
    drupal_migrate_source_url = models.CharField(
        "Адрес вставки в Drupal", max_length=2048
    )

    class Meta:
        verbose_name = "Использование файла Drupal"
        verbose_name_plural = "Использования файлов Drupal"
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "drupal_article",
                    "drupal_migrate_field",
                    "drupal_migrate_position",
                ),
                name="drupal_unique_file_usage",
            )
        ]

    def __str__(self):
        return f"{self.drupal_article}: {self.drupal_file} ({self.drupal_migrate_position})"


class DrupalMigrateURL(models.Model):
    url = models.CharField("Старый путь", max_length=2048, unique=True)
    drupal_article = models.ForeignKey(
        DrupalMigrateArticles, on_delete=models.PROTECT, null=True, blank=True
    )
    drupal_file = models.ForeignKey(
        DrupalMigrateFileManaged, on_delete=models.PROTECT, null=True, blank=True
    )

    class Meta:
        verbose_name = "Старый URL"
        verbose_name_plural = "Старые URL"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(drupal_article__isnull=False, drupal_file__isnull=True)
                    | models.Q(drupal_article__isnull=True, drupal_file__isnull=False)
                ),
                name="drupal_url_exactly_one_source",
            )
        ]

    def __str__(self):
        return self.url

    def clean(self):
        super().clean()
        if not self.url.startswith("/") or self.url.startswith("//"):
            raise ValidationError({"url": "Нужен путь от корня сайта."})
        if "?" in self.url or "#" in self.url:
            raise ValidationError({"url": "Путь не должен содержать query или якорь."})
