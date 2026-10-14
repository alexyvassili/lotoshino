"""Import reviewed archive files verbatim, without generating image sizes."""

from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from html import escape
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils.html import linebreaks, urlize
from PIL import Image as PillowImage

from article_collections.models import Collection, CollectionItem
from articles.models import Article
from document_library.models import Document
from document_library.validation import validate_document
from media_library.models import Image, ImageRendition
from site_settings.formats import IMAGE_FORMATS, validate_format
from site_settings.uploads import validate_upload_size

from .models import (
    DrupalMigrateArticleMap,
    DrupalMigrateArticles,
    DrupalMigrateCollectionMap,
    DrupalMigrateFileManaged,
    DrupalMigrateFileMap,
    DrupalMigrateFileUsage,
    DrupalMigrateURL,
)

_written_files = ContextVar("drupal_written_files", default=None)


def source_snapshot(page):
    return {
        "drupal_migrate_node_id": page["nid"],
        "drupal_migrate_title": page["title"],
        "drupal_migrate_status": bool(page["status"]),
        "drupal_migrate_created": page["created"],
        "drupal_migrate_changed": page["changed"],
    }


def save_url(path, **target):
    entry = DrupalMigrateURL(url=path, **target)
    entry.full_clean()
    entry.save()


@contextmanager
def atomic_import():
    """Track storage writes even if the subsequent model INSERT fails."""
    written = []
    token = _written_files.set(written)
    try:
        with transaction.atomic():
            yield
    except Exception:
        for storage, name in reversed(written):
            storage.delete(name)
        raise
    finally:
        _written_files.reset(token)


def write_file(storage, name, data):
    written = _written_files.get()
    if written is None:
        raise RuntimeError("Archive writes require atomic_import")
    name = storage.save(name, ContentFile(data))
    written.append((storage, name))
    return name


def verify_file(spec, root, *, variant=False):
    path = (root / spec["path"].lstrip("/")).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("File is outside the archive root")
    if not path.is_file():
        raise ValueError(f"Source file disappeared: {spec['path']}")
    if not spec.get("approved_variant" if variant else "approved_as_master"):
        raise ValueError(f"Source must be reviewed: {spec['path']}")
    if spec.get("fid") is None and not spec.get("allow_unmanaged"):
        raise ValueError(f"Unregistered source needs a decision: {spec['path']}")
    data = path.read_bytes()
    if sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError(f"Source changed since review: {spec['path']}")
    validate_upload_size(SimpleUploadedFile(path.name, data))
    with PillowImage.open(path) as original:
        validate_format(path.name, original.format, IMAGE_FORMATS)
        if original.width * original.height > 25_000_000:
            raise ValueError("Image exceeds 25 megapixels")
        dimensions = original.size
        mime = PillowImage.MIME[original.format]
        original.verify()
    return path, data, dimensions, mime


def metadata_for(spec, verified, **target):
    path, data, dimensions, mime = verified
    metadata = DrupalMigrateFileManaged.objects.create(
        drupal_migrate_file_id=spec.get("fid"),
        drupal_migrate_filename=spec.get("filename", path.name),
        drupal_migrate_timestamp=spec.get("timestamp"),
        drupal_migrate_filemime=spec.get("filemime", mime),
        drupal_migrate_filesize=spec.get("filesize", len(data)),
        drupal_migrate_width=dimensions[0],
        drupal_migrate_height=dimensions[1],
    )
    DrupalMigrateFileMap.objects.create(drupal_file=metadata, **target)
    save_url(spec["path"], drupal_file=metadata)
    return metadata


def existing_file(spec):
    old_url = DrupalMigrateURL.objects.filter(url=spec["path"]).first()
    if old_url:
        if not old_url.drupal_file_id:
            raise ValueError("The old file URL already points to a page")
        return old_url.drupal_file
    if spec.get("fid") is not None:
        metadata = DrupalMigrateFileManaged.objects.filter(
            drupal_migrate_file_id=spec["fid"]
        ).first()
        if metadata:
            save_url(spec["path"], drupal_file=metadata)
            return metadata
    return None


def file_bytes(file):
    with file.storage.open(file.name, "rb") as stream:
        return stream.read()


def verify_document(spec, root):
    path = (root / spec["path"].lstrip("/")).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Document is missing or outside the archive root")
    if not spec.get("approved_as_master"):
        raise ValueError("Document must be reviewed")
    if spec.get("fid") is None and not spec.get("allow_unmanaged"):
        raise ValueError("Unregistered document needs a decision")
    data = path.read_bytes()
    if sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError("Document changed since review")
    file_format = validate_document(SimpleUploadedFile(path.name, data))
    return path, data, file_format


def import_document(spec, root):
    path, data, file_format = verify_document(spec, root)
    metadata = existing_file(spec)
    if metadata:
        document = metadata.file_map.document
        if document is None or file_bytes(document.file) != data:
            raise ValueError("Existing document mapping does not match the archive")
        return document, metadata
    document = Document(
        title=spec["title"], original_name=path.name, file_format=file_format
    )
    document.file = write_file(
        document.file.storage, f"documents/{uuid4()}{path.suffix.lower()}", data
    )
    document.save()
    metadata = metadata_for(
        spec, (path, data, (None, None), spec["filemime"]), document=document
    )
    return document, metadata


def import_image(spec, root):
    verified = verify_file(spec, root)
    metadata = existing_file(spec)
    if metadata:
        mapping = metadata.file_map
        if not mapping.image_id or file_bytes(mapping.image.file) != verified[1]:
            raise ValueError("Existing master mapping does not match the archive")
        return mapping.image, metadata
    _, data, (width, height), mime = verified
    image = Image(title=spec["title"], alt_text=spec.get("alt", ""))
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[mime]
    stem = str(uuid4())
    # If the archive contains only a thumbnail, don't label its filename as an original.
    if spec.get("thumbnail_only"):
        stem += f"_{width}x{height}"
    image.file = write_file(image.file.storage, f"images/{stem}.{extension}", data)
    image.save()
    metadata = metadata_for(spec, verified, image=image)
    return image, metadata


def import_variant(spec, root, image):
    verified = verify_file(spec, root, variant=True)
    metadata = existing_file(spec)
    if metadata:
        version = metadata.file_map.rendition
        if (
            version is None
            or version.image_id != image.pk
            or file_bytes(version.file) != verified[1]
        ):
            raise ValueError("Existing variant mapping does not match the archive")
        return version, metadata
    _, data, (width, height), mime = verified
    version = image.renditions.filter(
        source_name=image.file.name,
        kind=ImageRendition.Kind.IMPORTED,
        max_width=width,
        max_height=height,
    ).first()
    if version:
        if file_bytes(version.file) != data:
            # Never overwrite a different crop with the same dimensions.
            raise ValueError(
                f"Different archive images have identical dimensions: {spec['path']}"
            )
    else:
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[
            mime
        ]
        stem = Path(image.file.name).stem.split("_")[0]
        version = ImageRendition(
            image=image,
            source_name=image.file.name,
            kind=ImageRendition.Kind.IMPORTED,
            max_width=width,
            max_height=height,
            width=width,
            height=height,
        )
        version.file = write_file(
            version.file.storage, f"images/{stem}_{width}x{height}.{extension}", data
        )
        version.save()
    metadata = metadata_for(spec, verified, rendition=version)
    return version, metadata


def import_versions(spec, root):
    image, master_metadata = import_image(spec, root)
    display, display_metadata = image, master_metadata
    if spec.get("display") and spec["display"]["path"] != spec["path"]:
        display, display_metadata = import_variant(spec["display"], root, image)
    return image, master_metadata, display, display_metadata


def save_usage(source, metadata, usage):
    DrupalMigrateFileUsage.objects.create(
        drupal_article=source,
        drupal_file=metadata,
        **{f"drupal_migrate_{name}": value for name, value in usage.items()},
    )


def import_article(page, root):
    existing = (
        DrupalMigrateArticleMap.objects.filter(
            drupal_article__drupal_migrate_node_id=page["nid"]
        )
        .select_related("article")
        .first()
    )
    if existing:
        return existing.article, False
    with atomic_import():
        source = DrupalMigrateArticles.objects.create(**source_snapshot(page))
        content = page["html"]
        for key, spec in page.get("images", {}).items():
            if (
                f"{{{{image:{key}}}}}" not in content
                and f"{{{{full:{key}}}}}" not in content
            ):
                raise ValueError(f"Unused source file in article: {key}")
            image, master_metadata, display, display_metadata = import_versions(
                spec, root
            )
            width, height = spec.get("display_size") or (
                display.file.width,
                display.file.height,
            )
            alignment = spec.get("alignment", "left")
            if alignment not in {"left", "right", "center"}:
                raise ValueError("Unknown imported image alignment")
            figure = (
                f'<figure class="image image-style-align-{alignment}">'
                f'<img src="{escape(display.file.url, quote=True)}" '
                f'width="{width}" height="{height}" '
                f'alt="{escape(spec.get("alt", ""), quote=True)}" '
                'data-viewer="true" '
                f'data-full-size="{escape(image.file.url, quote=True)}"></figure>'
            )
            content = content.replace(f"{{{{image:{key}}}}}", figure)
            content = content.replace(
                f"{{{{full:{key}}}}}", escape(image.file.url, quote=True)
            )
            for usage in spec["usages"]:
                metadata = (
                    display_metadata
                    if usage["field"] == "body:image"
                    else master_metadata
                )
                save_usage(source, metadata, usage)
        for key, spec in page.get("documents", {}).items():
            placeholder = f"{{{{document:{key}}}}}"
            if placeholder not in content:
                raise ValueError(f"Unused document in article: {key}")
            document, metadata = import_document(spec, root)
            content = content.replace(
                placeholder, escape(document.get_link_url(), quote=True)
            )
            for usage in spec["usages"]:
                save_usage(source, metadata, usage)
        if any(token in content for token in ("{{image:", "{{full:", "{{document:")):
            raise ValueError("Unresolved file placeholder")
        article = Article.objects.create(
            title=page["title"],
            slug=page["slug"],
            content=content,
            is_published=bool(page["status"]),
        )
        DrupalMigrateArticleMap.objects.create(drupal_article=source, article=article)
        for path in page["urls"]:
            save_url(path, drupal_article=source)
    return article, True


def import_collection(page, root):
    existing = (
        DrupalMigrateCollectionMap.objects.filter(
            drupal_article__drupal_migrate_node_id=page["nid"]
        )
        .select_related("collection")
        .first()
    )
    if existing:
        return existing.collection, False
    with atomic_import():
        source = DrupalMigrateArticles.objects.create(**source_snapshot(page))
        collection = Collection.objects.create(
            title=page["title"],
            slug=page["slug"],
            introduction=linebreaks(urlize(escape(page.get("introduction", ""))))
            if page.get("introduction")
            else "",
            closing_text=linebreaks(urlize(escape(page.get("closing_text", ""))))
            if page.get("closing_text")
            else "",
            is_published=bool(page["status"]),
            template_name=page["template_name"],
        )
        for position, item in enumerate(page["items"]):
            article = DrupalMigrateArticleMap.objects.get(
                drupal_article__drupal_migrate_node_id=item["nid"]
            ).article
            image = preview = None
            if item.get("image"):
                image, _, display, metadata = import_versions(item["image"], root)
                if isinstance(display, ImageRendition):
                    preview = display
                else:
                    # A thumbnail-only source needs no second file or encoding.
                    preview, _ = image.renditions.get_or_create(
                        source_name=image.file.name,
                        kind=ImageRendition.Kind.IMPORTED,
                        max_width=image.file.width,
                        max_height=image.file.height,
                        defaults={
                            "width": image.file.width,
                            "height": image.file.height,
                            "file": image.file.name,
                        },
                    )
                save_usage(source, metadata, item["usage"])
            CollectionItem.objects.create(
                collection=collection,
                article=article,
                image=image,
                imported_preview=preview,
                title=item.get("title", ""),
                annotation=item["annotation"],
                image_caption=item.get("image_caption", ""),
                link_text=item.get("link_text", "Читать далее"),
                position=position,
            )
        DrupalMigrateCollectionMap.objects.create(
            drupal_article=source, collection=collection
        )
        for path in page["urls"]:
            save_url(path, drupal_article=source)
    return collection, True
