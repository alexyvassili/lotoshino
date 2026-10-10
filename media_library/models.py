from pathlib import Path
from uuid import uuid4

from django.db import models

from lotoshino.models import TimestampedModel


def image_upload_path(instance, filename):
    return f"images/{uuid4().hex}{Path(filename).suffix.lower()}"


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
