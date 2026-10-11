from django import forms
from django.core.files.uploadedfile import UploadedFile
from PIL import Image as PillowImage
from PIL import ImageOps, UnidentifiedImageError

from site_settings.formats import IMAGE_FORMATS, allowed_extensions, validate_format
from site_settings.uploads import validate_upload_size

from .models import Image, ImageSettings
from .processing import encode_image


class ImageForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs["accept"] = ",".join(
            allowed_extensions(IMAGE_FORMATS)
        )

    class Meta:
        model = Image
        fields = ("title", "file", "alt_text")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not isinstance(upload, UploadedFile):
            return upload
        validate_upload_size(upload)
        try:
            upload.seek(0)
            with PillowImage.open(upload) as image:
                validate_format(upload.name, image.format, IMAGE_FORMATS)
                if image.width * image.height > 25_000_000:
                    raise forms.ValidationError(
                        "Максимальное разрешение — 25 мегапикселей."
                    )
                file_format = image.format
                image = ImageOps.exif_transpose(image)
                image.load()
                settings = ImageSettings.load()
                image.thumbnail(
                    (settings.max_image_width, settings.max_image_height),
                    PillowImage.Resampling.LANCZOS,
                )
                return encode_image(image, file_format)
        except (
            OSError,
            ValueError,
            UnidentifiedImageError,
            PillowImage.DecompressionBombError,
        ) as exc:
            raise forms.ValidationError(
                "Изображение повреждено или имеет неподдерживаемый формат."
            ) from exc
