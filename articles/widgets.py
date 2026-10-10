from typing import ClassVar

from django import forms
from django.urls import reverse


class ArticleEditorWidget(forms.Textarea):
    template_name = "articles/widgets/editor.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"].update(
            {
                "data-article-editor": "true",
                "data-upload-url": reverse("admin:article_image_upload"),
                "data-library-url": reverse("admin:article_image_library"),
            }
        )
        return context

    class Media:
        css: ClassVar = {
            "all": (
                "vendor/ckeditor5/49.0.0/ckeditor5.css",
                "articles/content.css",
                "articles/editor.css",
            )
        }
        js = (
            "vendor/ckeditor5/49.0.0/ckeditor5.umd.js",
            "vendor/ckeditor5/49.0.0/translations/ru.umd.js",
            "articles/editor.js",
        )
