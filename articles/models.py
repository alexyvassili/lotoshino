from django.db import IntegrityError, models, router, transaction
from django.urls import reverse

from lotoshino.models import TimestampedModel

from .html import clean_article_html
from .slugs import article_slug_base, available_slug


class Article(TimestampedModel):
    title = models.CharField("Заголовок статьи", max_length=255)
    slug = models.SlugField(
        "Адрес статьи",
        max_length=255,
        unique=True,
        blank=True,
        help_text=(
            "Часть URL после /articles/. Латинские буквы, цифры, дефисы и подчёркивания. "
            "Если адрес не заполнен, он будет сгенерирован автоматически "
            "из заголовка латиницей при сохранении."
        ),
    )
    content = models.TextField("Текст статьи")

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("articles:detail", kwargs={"slug": self.slug})

    def save(self, **kwargs):
        if kwargs.get("update_fields") is not None and not kwargs["update_fields"]:
            return super().save(**kwargs)
        if kwargs.get("update_fields") is None or "content" in kwargs["update_fields"]:
            self.content = clean_article_html(self.content)
        if self.slug:
            return super().save(**kwargs)

        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        kwargs["using"] = using
        articles = type(self).objects.using(using)
        if not self._state.adding:
            articles = articles.exclude(pk=self.pk)
        base = article_slug_base(self.title)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"slug"}
        while True:
            self.slug = available_slug(
                base, articles, self._meta.get_field("slug").max_length
            )
            try:
                # A savepoint lets concurrent automatic slugs retry a unique collision.
                with transaction.atomic(using=using):
                    return super().save(**kwargs)
            except IntegrityError:
                if not articles.filter(slug=self.slug).exists():
                    raise
