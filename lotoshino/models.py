from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Изменено", auto_now=True)

    class Meta:
        abstract = True

    def save(self, **kwargs):
        if kwargs.get("update_fields"):
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"updated_at"}
        return super().save(**kwargs)
