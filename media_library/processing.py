from io import BytesIO

from django.core.files.base import ContentFile


def encode_image(image, file_format):
    """Keep the master and its derivatives at high encoding quality."""
    options = {}
    if file_format == "JPEG":
        options.update(quality=95, subsampling=0, optimize=True)
    elif file_format == "WEBP":
        options.update(quality=95, method=6)
    if image.info.get("icc_profile"):
        options["icc_profile"] = image.info["icc_profile"]
    output = BytesIO()
    image.save(output, format=file_format, **options)
    extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[file_format]
    return ContentFile(output.getvalue(), name=f"image.{extension}")
