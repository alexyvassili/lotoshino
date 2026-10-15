from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, models, router, transaction
from django.urls import Resolver404, resolve, reverse

from articles.html import clean_article_html
from articles.slugs import article_slug_base, available_slug
from lotoshino.models import TimestampedModel

from .layouts import DEFAULT_TEMPLATE, collection_template_choices


class Collection(TimestampedModel):
    title = models.CharField("Название", max_length=255)
    slug = models.SlugField(
        "Адрес",
        max_length=100,
        unique=True,
        blank=True,
        help_text=(
            "Часть адреса без слешей: например, history для /history/. "
            "Если адрес не заполнен, он будет сгенерирован автоматически "
            "из названия латиницей при сохранении."
        ),
    )
    introduction = models.TextField("Вступительный текст", blank=True)
    closing_text = models.TextField(
        "Заключительный текст",
        blank=True,
        help_text="Выводится после списка статей. Например, сведения об источнике материалов.",
    )
    is_published = models.BooleanField("Опубликовано", default=True)
    template_name = models.CharField(
        "Шаблон",
        max_length=255,
        choices=collection_template_choices,
        default=DEFAULT_TEMPLATE,
        help_text=(
            "Выбирается только при создании подборки. После сохранения можно "
            "редактировать сам файл шаблона; правки применятся ко всем "
            "подборкам, использующим этот файл."
        ),
    )

    class Meta:
        verbose_name = "Подборка статей"
        verbose_name_plural = "Подборки статей"
        ordering = ("title", "pk")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("article_collection", kwargs={"slug": self.slug})

    @staticmethod
    def is_reserved_slug(slug):
        if slug in {"admin", "articles", "documents", "media", "static", "__debug__"}:
            return True
        try:
            match = resolve(f"/{slug}/")
        except Resolver404:
            return False
        return match.view_name != "article_collection"

    def clean(self):
        super().clean()
        self._validate_template()
        if self.slug and self.is_reserved_slug(self.slug):
            raise ValidationError(
                {
                    "slug": "Этот адрес занят служебным разделом или другой страницей сайта."
                }
            )

    def _validate_template(self, using=None):
        using = (
            using or self._state.db or router.db_for_write(type(self), instance=self)
        )
        if not self._state.adding:
            original = (
                type(self)
                .objects.using(using)
                .filter(pk=self.pk)
                .values_list("template_name", flat=True)
                .first()
            )
            if original is not None and self.template_name != original:
                raise ValidationError(
                    {"template_name": "Шаблон нельзя изменить после создания подборки."}
                )
        elif self.template_name not in dict(collection_template_choices()):
            raise ValidationError(
                {"template_name": "Выберите доступный шаблон подборки."}
            )

    def save(self, **kwargs):
        if kwargs.get("update_fields") is not None and not kwargs["update_fields"]:
            return super().save(**kwargs)
        for name in ("introduction", "closing_text"):
            if kwargs.get("update_fields") is None or name in kwargs["update_fields"]:
                setattr(self, name, clean_article_html(getattr(self, name)))
        if (
            kwargs.get("update_fields") is None
            or "template_name" in kwargs["update_fields"]
        ):
            self._validate_template(using=kwargs.get("using"))
        if self.slug:
            return super().save(**kwargs)

        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        kwargs["using"] = using
        collections = type(self).objects.using(using)
        if not self._state.adding:
            collections = collections.exclude(pk=self.pk)
        base = article_slug_base(self.title)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"slug"}
        while True:
            self.slug = available_slug(
                base,
                collections,
                self._meta.get_field("slug").max_length,
                is_reserved=self.is_reserved_slug,
            )
            try:
                # Retry only a concurrent collision on an automatically chosen URL.
                with transaction.atomic(using=using):
                    return super().save(**kwargs)
            except IntegrityError:
                if not collections.filter(slug=self.slug).exists():
                    raise


class CollectionItem(models.Model):
    collection = models.ForeignKey(
        Collection, on_delete=models.CASCADE, related_name="items"
    )
    article = models.ForeignKey(
        "articles.Article",
        verbose_name="Статья",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Выберите статью или заполните внешнюю ссылку ниже.",
    )
    external_url = models.URLField(
        "Внешняя ссылка",
        max_length=2048,
        blank=True,
        validators=[URLValidator(schemes=["http", "https"])],
        help_text="Для карточки другого сайта. Оставьте поле «Статья» пустым; аннотация станет текстом ссылки.",
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
    image_caption = models.CharField(
        "Подпись под изображением",
        max_length=255,
        blank=True,
        help_text="Например, годы жизни для портрета.",
    )
    imported_preview = models.ForeignKey(
        "media_library.ImageRendition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="collection_items",
    )
    link_text = models.CharField(
        "Текст ссылки",
        max_length=100,
        default="Читать далее",
        blank=True,
        help_text="Оставьте пустым, чтобы не показывать отдельную ссылку под аннотацией.",
    )
    is_new = models.BooleanField("Новая статья", default=False)
    position = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Карточка статьи в подборке"
        verbose_name_plural = "Карточки статей в подборке"
        ordering = ("position", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("collection", "article"), name="unique_collection_article"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(article__isnull=False, external_url="")
                    | (models.Q(article__isnull=True) & ~models.Q(external_url=""))
                ),
                name="collection_item_one_destination",
            ),
        ]

    def __str__(self):
        return self.title or (
            str(self.article) if self.article_id else self.external_url
        )

    def save(self, **kwargs):
        self.clean()
        if not self.title.strip() and self.article_id:
            self.title = self.article.title
        if self.imported_preview_id and self.imported_preview.image_id != self.image_id:
            self.imported_preview = None
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                    "imported_preview"
                }
        super().save(**kwargs)

    def get_absolute_url(self):
        return self.article.get_absolute_url() if self.article_id else self.external_url

    def clean(self):
        super().clean()
        if bool(self.article_id) == bool(self.external_url):
            raise ValidationError(
                "Выберите статью или укажите внешнюю ссылку — только один вариант."
            )
        if self.external_url:
            try:
                URLValidator(schemes=["http", "https"])(self.external_url)
            except ValidationError as error:
                raise ValidationError({"external_url": error.messages}) from error
            if not self.title.strip():
                raise ValidationError({"title": "Укажите название карточки."})
