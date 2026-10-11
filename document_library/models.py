from pathlib import Path
from uuid import uuid4

from django.db import models
from django.urls import reverse

from lotoshino.models import TimestampedModel


def document_upload_path(instance, filename):
    return f"documents/{uuid4().hex}{Path(filename).suffix.lower()}"


class Document(TimestampedModel):
    title = models.CharField("Название", max_length=255)
    file = models.FileField("Документ", upload_to=document_upload_path)
    original_name = models.CharField("Имя файла", max_length=255, editable=False)
    file_format = models.CharField("Формат", max_length=8, editable=False)

    class Meta:
        verbose_name = "Документ"
        verbose_name_plural = "Документы"
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("document_download", args=[self.pk])
