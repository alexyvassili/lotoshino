from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models


def validate_menu_url(value):
    if not value:
        return
    if "\\" in value or any(
        char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise ValidationError("Укажите корректный адрес без пробелов.")
    if value.startswith("/") and not value.startswith("//"):
        return
    URLValidator(schemes=["http", "https"])(value)


class Menu(models.Model):
    class Code(models.TextChoices):
        MAIN = "main", "Главное"
        TOP = "top", "Верхнее"

    code = models.CharField("Меню", max_length=4, choices=Code, primary_key=True)

    class Meta:
        verbose_name = "Меню"
        verbose_name_plural = "Меню"
        ordering = ("code",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__in=["main", "top"]), name="menu_known_code"
            )
        ]

    def __str__(self):
        return self.get_code_display()


class MenuItem(models.Model):
    menu = models.ForeignKey(Menu, related_name="items", on_delete=models.CASCADE)
    title = models.CharField("Название", max_length=255)
    home_page = models.ForeignKey(
        "home.HomePage", null=True, blank=True, on_delete=models.SET_NULL
    )
    article = models.ForeignKey(
        "articles.Article", null=True, blank=True, on_delete=models.SET_NULL
    )
    collection = models.ForeignKey(
        "article_collections.Collection",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    url = models.CharField(
        "Свой URL",
        max_length=2048,
        blank=True,
        validators=[validate_menu_url],
        help_text="Например, /history/ или https://example.org/. Заполните вместо выбора страницы.",
    )
    is_visible = models.BooleanField("Показывать в меню", default=True)
    position = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Пункт меню"
        verbose_name_plural = "Пункты меню"
        ordering = ("position", "pk")

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        count = sum(
            bool(value)
            for value in (
                self.home_page_id,
                self.article_id,
                self.collection_id,
                self.url,
            )
        )
        if count != 1:
            raise ValidationError(
                "Выберите страницу или укажите свой URL — один из двух вариантов."
            )

    def get_destination(self):
        if self.home_page_id:
            return self.home_page.get_absolute_url()
        if self.article_id:
            return (
                self.article.get_absolute_url() if self.article.is_published else None
            )
        if self.collection_id:
            return (
                self.collection.get_absolute_url()
                if self.collection.is_published
                else None
            )
        if self.url:
            try:
                validate_menu_url(self.url)
            except ValidationError:
                return None
            return self.url
        return None

    def is_current(self, request_path, destination):
        parsed = urlsplit(destination)
        return (
            not parsed.netloc
            and not parsed.fragment
            and not parsed.query
            and parsed.path == request_path
        )
