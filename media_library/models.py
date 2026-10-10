from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from lotoshino.models import TimestampedModel


def image_upload_path(instance, filename):
    return f"images/{uuid4().hex}{Path(filename).suffix.lower()}"


def dimension_field(label, default):
    return models.PositiveSmallIntegerField(
        label,
        default=default,
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
    )


class ImageSettings(TimestampedModel):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    max_image_width = dimension_field("Максимальная ширина, px", 2560)
    max_image_height = dimension_field("Максимальная высота, px", 2560)
    gallery_preview_width = dimension_field("Ширина превью, px", 400)
    gallery_preview_height = dimension_field("Высота превью, px", 300)
    gallery_full_width = dimension_field("Ширина полного изображения, px", 2048)
    gallery_full_height = dimension_field("Высота полного изображения, px", 1536)
    gallery_portrait_preview_width = dimension_field("Ширина превью, px", 300)
    gallery_portrait_preview_height = dimension_field("Высота превью, px", 400)
    gallery_portrait_full_width = dimension_field(
        "Ширина полного изображения, px", 1536
    )
    gallery_portrait_full_height = dimension_field(
        "Высота полного изображения, px", 2048
    )
    article_preview_width = dimension_field("Ширина превью, px", 320)
    article_preview_height = dimension_field("Высота превью, px", 240)
    article_full_width = dimension_field("Ширина полного изображения, px", 1280)
    article_full_height = dimension_field("Высота полного изображения, px", 960)
    article_portrait_preview_width = dimension_field("Ширина превью, px", 240)
    article_portrait_preview_height = dimension_field("Высота превью, px", 360)
    article_portrait_full_width = dimension_field("Ширина полного изображения, px", 960)
    article_portrait_full_height = dimension_field(
        "Высота полного изображения, px", 1440
    )

    class Meta:
        verbose_name = "Настройки изображений"
        verbose_name_plural = "Настройки изображений"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="image_settings_singleton"
            )
        ]

    def __str__(self):
        return "Настройки изображений"

    @classmethod
    def load(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def clean(self):
        super().clean()
        errors = {}
        for prefix in ("gallery", "gallery_portrait", "article", "article_portrait"):
            for axis in ("width", "height"):
                preview_field = f"{prefix}_preview_{axis}"
                preview = getattr(self, preview_field)
                full = getattr(self, f"{prefix}_full_{axis}")
                if preview is not None and full is not None and preview > full:
                    errors[preview_field] = (
                        "Размер превью не должен превышать соответствующий размер "
                        "полного изображения."
                    )
                maximum = getattr(self, f"max_image_{axis}")
                if full is not None and maximum is not None and full > maximum:
                    errors[f"{prefix}_full_{axis}"] = (
                        "Размер полной версии не должен превышать общий максимум "
                        "по соответствующей стороне."
                    )
        if errors:
            raise ValidationError(errors)


class Image(TimestampedModel):
    title = models.CharField("Название", max_length=255)
    file = models.ImageField("Изображение", upload_to=image_upload_path)
    alt_text = models.CharField("Описание для доступности", max_length=255, blank=True)

    class Meta:
        verbose_name = "Изображение"
        verbose_name_plural = "Изображения"
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return self.title


class ImageRendition(TimestampedModel):
    class Kind(models.TextChoices):
        ARTICLE_PREVIEW = "article_preview", "Статья — превью"
        ARTICLE_FULL = "article_full", "Статья — полная версия"

    image = models.ForeignKey(
        Image, on_delete=models.CASCADE, related_name="renditions"
    )
    source_name = models.CharField(max_length=100)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    max_width = models.PositiveSmallIntegerField()
    max_height = models.PositiveSmallIntegerField()
    width = models.PositiveSmallIntegerField()
    height = models.PositiveSmallIntegerField()
    file = models.ImageField(upload_to=image_upload_path)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("image", "source_name", "kind", "max_width", "max_height"),
                name="unique_image_rendition",
            )
        ]
