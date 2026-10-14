"""Flat public image names with UUID-prefix directories on the local filesystem."""

import re
from pathlib import PurePosixPath

from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

IMAGE_FILENAME = re.compile(
    r"(?:[a-f0-9]{32}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})"
    r"(?:_[A-Za-z0-9]{7})?"
    r"(?:_[1-9]\d{0,4}x[1-9]\d{0,4}(?:_[A-Za-z0-9]{7})?)?"
    r"\.(?:jpg|jpeg|png|webp)"
)


def logical_image_name(name):
    parts = PurePosixPath(name).parts
    if (
        len(parts) == 3
        and parts[0] == "images"
        and IMAGE_FILENAME.fullmatch(parts[2])
        and parts[1] == parts[2][:2]
    ):
        return f"images/{parts[2]}"
    return name


def physical_image_name(name):
    name = logical_image_name(name)
    parts = PurePosixPath(name).parts
    if len(parts) == 2 and parts[0] == "images" and IMAGE_FILENAME.fullmatch(parts[1]):
        return f"images/{parts[1][:2]}/{parts[1]}"
    return name


@deconstructible
class ImageStorage(FileSystemStorage):
    def path(self, name):
        return super().path(physical_image_name(name))

    def _save(self, name, content):
        # FileSystemStorage returns the physical path relative to MEDIA_ROOT.
        # Keep the database name flat, including any collision suffix it chose.
        return logical_image_name(super()._save(name, content))

    def url(self, name):
        return super().url(logical_image_name(name))


image_storage = ImageStorage()
