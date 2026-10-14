from typing import ClassVar

from django import forms

from articles.html import clean_article_html
from articles.illustrations import ILLUSTRATION_ERROR, has_invalid_illustrations

from .layouts import TEXT_TEMPLATE
from .models import Collection, CollectionItem
from .widgets import CollectionEditorWidget, CollectionImageWidget


class CollectionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        template = self.data.get("template_name") if self.is_bound else None
        if (template or self.instance.template_name) == TEXT_TEMPLATE:
            self.fields["introduction"].label = "Содержимое"

    class Meta:
        model = Collection
        fields = (
            "title",
            "slug",
            "template_name",
            "introduction",
            "closing_text",
            "is_published",
        )
        widgets: ClassVar = {
            "introduction": CollectionEditorWidget,
            "closing_text": CollectionEditorWidget,
        }

    def clean(self):
        data = super().clean()
        for name in ("introduction", "closing_text"):
            value = data.get(name, "")
            if has_invalid_illustrations(value):
                self.add_error(name, ILLUSTRATION_ERROR)
            else:
                data[name] = clean_article_html(value)
        return data


class CollectionItemForm(forms.ModelForm):
    class Meta:
        model = CollectionItem
        fields = (
            "collection",
            "article",
            "title",
            "image",
            "image_caption",
            "annotation",
            "link_text",
            "is_new",
            "position",
        )
        widgets: ClassVar = {
            "image": CollectionImageWidget,
            "annotation": forms.Textarea(attrs={"rows": 4}),
            "position": forms.HiddenInput,
        }

    def clean(self):
        data = super().clean()
        article = data.get("article")
        if article and not data.get("title", "").strip():
            data["title"] = article.title
        return data
