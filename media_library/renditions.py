from django.db import transaction
from PIL import Image as PillowImage
from PIL import ImageOps

from .models import Image, ImageRendition, ImageSettings
from .processing import encode_image


def article_renditions(image):
    """Generate each size directly from the master, retaining previous versions."""
    settings = ImageSettings.load()
    with transaction.atomic():
        image = Image.objects.select_for_update().get(pk=image.pk)
        with (
            image.file.storage.open(image.file.name, "rb") as file,
            PillowImage.open(file) as original,
        ):
            file_format = original.format
            if file_format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Unsupported image format")
            source = ImageOps.exif_transpose(original)
            source.load()
        prefix = "article_portrait" if source.height > source.width else "article"
        result = {}
        for size in ("preview", "full"):
            bounds = (
                getattr(settings, f"{prefix}_{size}_width"),
                getattr(settings, f"{prefix}_{size}_height"),
            )
            lookup = {
                "image": image,
                "source_name": image.file.name,
                "kind": f"article_{size}",
                "max_width": bounds[0],
                "max_height": bounds[1],
            }
            rendition = ImageRendition.objects.filter(**lookup).first()
            if rendition is None or not rendition.file.storage.exists(
                rendition.file.name
            ):
                resized = source.copy()
                resized.thumbnail(bounds, PillowImage.Resampling.LANCZOS)
                rendition = rendition or ImageRendition(**lookup)
                rendition.width, rendition.height = resized.size
                # Different profiles can produce identical actual dimensions.
                # Share the existing file instead of creating a suffixed duplicate.
                matching = ImageRendition.objects.filter(
                    image=image,
                    source_name=image.file.name,
                    width=rendition.width,
                    height=rendition.height,
                )
                reusable = next(
                    (
                        version
                        for version in matching
                        if version.file.storage.exists(version.file.name)
                    ),
                    None,
                )
                rendition.file = (
                    reusable.file.name
                    if reusable
                    else encode_image(resized, file_format)
                )
                rendition.save()
            result[size] = rendition
    return result


def article_image_data(image):
    # GIFs can only arrive through reviewed archive imports. Reuse their bytes
    # when selected again, preserving animation instead of making static sizes.
    if image.file.name.lower().endswith(".gif"):
        with (
            image.file.storage.open(image.file.name, "rb") as file,
            PillowImage.open(file) as original,
        ):
            if original.format != "GIF":
                raise ValueError("Unsupported image format")
            width, height = original.size
        return {
            "id": image.pk,
            "url": image.file.url,
            "full_url": image.file.url,
            "width": width,
            "height": height,
            "alt": image.alt_text,
        }
    versions = article_renditions(image)
    preview, full = versions["preview"], versions["full"]
    return {
        "id": image.pk,
        "url": preview.file.url,
        "full_url": full.file.url,
        "width": preview.width,
        "height": preview.height,
        "alt": image.alt_text,
    }
