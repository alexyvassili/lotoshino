from typing import ClassVar

from django import forms

from article_collections.models import Collection
from articles.models import Article
from home.models import HomePage

from .models import MenuItem


class PageSelect(forms.Select):
    def create_option(
        self, name, value, label, selected, index, subindex=None, attrs=None
    ):
        option = super().create_option(
            name, value, label, selected, index, subindex, attrs
        )
        if value:
            option["attrs"]["data-title"] = self.page_titles.get(str(value), "")
        return option


class MenuItemForm(forms.ModelForm):
    page = forms.ChoiceField(
        label="Страница сайта",
        required=False,
        choices=(),
        widget=PageSelect,
        help_text="Ссылка обновится автоматически при изменении адреса выбранной страницы.",
    )

    class Meta:
        model = MenuItem
        fields = ("title", "page", "url", "is_visible", "position")
        widgets: ClassVar = {
            "position": forms.HiddenInput,
            "url": forms.TextInput(
                attrs={"placeholder": "/history/ или https://example.org/"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["page"].widget.page_titles = {}

        def label(page, kind):
            self.fields["page"].widget.page_titles[f"{kind}:{page.pk}"] = page.title
            return page.title + (
                " — не опубликовано" if not getattr(page, "is_published", True) else ""
            )

        self.fields["page"].choices = [
            ("", "— Выберите страницу —"),
            (
                "Главная страница",
                [
                    (f"home_page:{page.pk}", label(page, "home_page"))
                    for page in HomePage.objects.all()
                ],
            ),
            (
                "Подборки статей",
                [
                    (f"collection:{page.pk}", label(page, "collection"))
                    for page in Collection.objects.all()
                ],
            ),
            (
                "Статьи",
                [
                    (f"article:{page.pk}", label(page, "article"))
                    for page in Article.objects.order_by("title", "pk")
                ],
            ),
        ]
        if self.instance.pk:
            for field in ("home_page", "article", "collection"):
                if pk := getattr(self.instance, f"{field}_id"):
                    self.initial["page"] = f"{field}:{pk}"
                    break

    def clean(self):
        data = super().clean()
        for field in ("home_page_id", "article_id", "collection_id"):
            setattr(self.instance, field, None)
        if page := data.get("page"):
            field, pk = page.split(":", 1)
            setattr(self.instance, f"{field}_id", int(pk))
        return data
