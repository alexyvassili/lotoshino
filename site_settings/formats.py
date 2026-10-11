from pathlib import Path

from django.core.exceptions import ValidationError

from .models import SiteSettings

IMAGE_FORMATS = {
    "JPEG": ("allow_image_jpeg", (".jpg", ".jpeg")),
    "PNG": ("allow_image_png", (".png",)),
    "WEBP": ("allow_image_webp", (".webp",)),
}
DOCUMENT_FORMATS = {
    name.upper(): (f"allow_file_{name}", (f".{name}",))
    for name in ("doc", "docx", "odt", "pdf", "rtf")
}


def allowed_extensions(formats):
    settings = SiteSettings.load()
    return [
        extension
        for field, extensions in formats.values()
        if getattr(settings, field)
        for extension in extensions
    ]


def validate_format(filename, detected_format, formats):
    if detected_format not in formats:
        raise ValidationError("Формат файла не поддерживается.")
    field, extensions = formats[detected_format]
    if Path(filename).suffix.lower() not in extensions:
        raise ValidationError("Расширение файла не соответствует содержимому.")
    if not getattr(SiteSettings.load(), field):
        raise ValidationError(
            f"Загрузка файлов {detected_format} отключена в настройках сайта."
        )
