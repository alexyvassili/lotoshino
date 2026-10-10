from django.core.validators import MinValueValidator
from django.db import models

from lotoshino.models import TimestampedModel


class SiteSettings(TimestampedModel):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    max_upload_size_mb = models.PositiveIntegerField(
        "Максимальный размер файла для загрузки, МБ",
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Лимит одного файла любого типа: изображения, документа и других файлов.",
    )

    class Meta:
        verbose_name = "Настройки"
        verbose_name_plural = "Настройки"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="site_settings_singleton"
            )
        ]

    def __str__(self):
        return "Настройки"

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    @property
    def max_upload_size_bytes(self):
        return self.max_upload_size_mb * 1024 * 1024
