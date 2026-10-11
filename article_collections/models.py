from django.core.exceptions import ValidationError
from django.db import models
from django.urls import Resolver404, resolve, reverse

from lotoshino.models import TimestampedModel


class Collection(TimestampedModel):
    title = models.CharField("Название", max_length=255)
    slug = models.SlugField(
        "Адрес",
        max_length=100,
        unique=True,
        help_text="Часть адреса без слешей: например, history для /history/.",
    )
    introduction = models.TextField("Вступительный текст", blank=True)
    is_published = models.BooleanField("Опубликовано", default=True)

    class Meta:
        verbose_name = "Подборка статей"
        verbose_name_plural = "Подборки статей"
        ordering = ("title", "pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("article_collection", kwargs={"slug": self.slug})

    def clean(self):
        super().clean()
        if self.slug in {
            "admin",
            "articles",
            "documents",
            "media",
            "static",
            "__debug__",
        }:
            raise ValidationError(
                {"slug": "Этот адрес занят служебным разделом сайта."}
            )
        if not self.slug:
            return
        try:
            match = resolve(f"/{self.slug}/")
        except Resolver404:
            return
        if match.view_name != "article_collection":
            raise ValidationError(
                {"slug": "Этот адрес уже используется другой страницей сайта."}
            )


class CollectionItem(models.Model):
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="items"
    )
    article = models.ForeignKey(
        "articles.Article", verbose_name="Статья", on_delete=models.PROTECT
    )
    title = models.CharField(
        "Название",
        max_length=255,
        blank=True,
        help_text="Подставляется из статьи; можно задать другое название для этой подборки.",
    )
    image = models.ForeignKey(
        "media_library.Image",
        verbose_name="Изображение",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    annotation = models.TextField("Аннотация")
    link_text = models.CharField("Текст ссылки", max_length=100, default="Читать далее")
    position = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Статья подборки"
        verbose_name_plural = "Статьи подборки"
        ordering = ("position", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("collection", "article"), name="unique_collection_article"
            )
        ]

    def __str__(self):
        return self.title or str(self.article)

    def save(self, **kwargs):
        if not self.title.strip():
            self.title = self.article.title
        super().save(**kwargs)
