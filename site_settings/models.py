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
    allow_image_jpeg = models.BooleanField("JPEG (.jpg, .jpeg)", default=True)
    allow_image_png = models.BooleanField("PNG (.png)", default=True)
    allow_image_webp = models.BooleanField("WebP (.webp)", default=True)
    allow_file_doc = models.BooleanField("DOC (.doc)", default=True)
    allow_file_docx = models.BooleanField("DOCX (.docx)", default=True)
    allow_file_odt = models.BooleanField("ODT (.odt)", default=True)
    allow_file_pdf = models.BooleanField("PDF (.pdf)", default=True)
    allow_file_rtf = models.BooleanField("RTF (.rtf)", default=True)

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
