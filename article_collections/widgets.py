from django import forms
from django.urls import reverse

from media_library.models import Image
from site_settings.formats import IMAGE_FORMATS, allowed_extensions

from .images import picker_image


class CollectionImageWidget(forms.HiddenInput):
    is_hidden = False
    template_name = "article_collections/widgets/image.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        try:
            image = Image.objects.filter(pk=value).first() if value else None
        except ValueError, TypeError, OverflowError:
            image = None
        context.update(
            {
                "selected_image": picker_image(image) if image else None,
                "picker_url": reverse("admin:collection_image_picker"),
                "upload_url": reverse("admin:collection_image_upload"),
                "prepare_url": reverse("admin:collection_image_prepare", args=[0]),
                "image_types": ",".join(allowed_extensions(IMAGE_FORMATS)),
            }
        )
        return context
