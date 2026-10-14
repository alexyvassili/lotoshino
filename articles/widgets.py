from typing import ClassVar

from django import forms
from django.urls import reverse

from site_settings.formats import IMAGE_FORMATS, allowed_extensions


class ArticleEditorWidget(forms.Textarea):
    template_name = "articles/widgets/editor.html"
    upload_url_name = "admin:article_image_upload"
    library_url_name = "admin:article_image_library"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["attrs"].update(
            {
                "data-article-editor": "true",
                "data-upload-url": reverse(self.upload_url_name),
                "data-library-url": reverse(self.library_url_name),
                "data-image-types": ",".join(
                    extension.lstrip(".").replace("jpg", "jpeg")
                    for extension in allowed_extensions(IMAGE_FORMATS)
                    if extension != ".jpeg"
                ),
            }
        )
        return context

    class Media:
        css: ClassVar = {
            "all": (
                "vendor/ckeditor5/49.0.0/ckeditor5.css",
                "articles/content.css?v=5",
                "articles/editor.css?v=2",
            )
        }
        js = (
            "vendor/ckeditor5/49.0.0/ckeditor5.umd.js",
            "vendor/ckeditor5/49.0.0/translations/ru.umd.js",
            "articles/editor.js?v=5",
        )
