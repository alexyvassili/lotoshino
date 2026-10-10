from io import BytesIO

from django import forms
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image as PillowImage
from PIL import ImageOps, UnidentifiedImageError

from .models import Image


class ImageForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = ("title", "file", "alt_text")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not isinstance(upload, UploadedFile):
            return upload
        if upload.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Максимальный размер изображения — 10 МБ.")
        try:
            upload.seek(0)
            with PillowImage.open(upload) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise forms.ValidationError(
                        "Выберите изображение JPEG, PNG или WebP."
                    )
                if image.width * image.height > 25_000_000:
                    raise forms.ValidationError(
                        "Максимальное разрешение — 25 мегапикселей."
                    )
                file_format = image.format
                image = ImageOps.exif_transpose(image)
                image.load()
                output = BytesIO()
                image.save(output, format=file_format)
            extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[file_format]
            return ContentFile(output.getvalue(), name=f"image.{extension}")
        except (
            OSError,
            ValueError,
            UnidentifiedImageError,
            PillowImage.DecompressionBombError,
        ) as exc:
            raise forms.ValidationError(
                "Изображение повреждено или имеет неподдерживаемый формат."
            ) from exc
