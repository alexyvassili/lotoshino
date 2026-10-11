from typing import ClassVar

from django import forms

from .models import CollectionItem
from .widgets import CollectionImageWidget


class CollectionItemForm(forms.ModelForm):
    class Meta:
        model = CollectionItem
        fields = (
            "collection",
            "article",
            "title",
            "image",
            "annotation",
            "link_text",
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
