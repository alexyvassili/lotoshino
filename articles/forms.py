import re
from html import unescape
from typing import ClassVar

from django import forms
from django.utils.html import strip_tags

from .html import clean_article_html
from .illustrations import ILLUSTRATION_ERROR, has_invalid_illustrations
from .models import Article
from .widgets import ArticleEditorWidget


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ("title", "slug", "content")
        widgets: ClassVar = {"content": ArticleEditorWidget}

    def clean_content(self):
        if has_invalid_illustrations(self.cleaned_data["content"]):
            raise forms.ValidationError(ILLUSTRATION_ERROR)
        content = clean_article_html(self.cleaned_data["content"])
        if not unescape(strip_tags(content)).strip() and not re.search(
            r'<img\b[^>]*\ssrc="', content
        ):
            raise forms.ValidationError(
                "Введите текст статьи или вставьте изображение."
            )
        return content
