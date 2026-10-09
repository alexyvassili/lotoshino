from django.db import models

from lotoshino.models import TimestampedModel


class HomePage(TimestampedModel):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    title = models.CharField(
        "Заголовок", max_length=255, default="Лотошинский церковный округ"
    )
    content = models.TextField(
        "Вступительный текст",
        blank=True,
        help_text="Пока не используется: содержимое главной задано в шаблоне.",
    )
    seo_title = models.CharField("SEO-заголовок", max_length=255, blank=True)
    seo_description = models.TextField("SEO-описание", blank=True)

    class Meta:
        verbose_name = "Главная страница"
        verbose_name_plural = "Главная страница"
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="home_page_singleton")
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return "/"
