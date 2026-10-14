import re
from pathlib import PurePosixPath
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from article_collections.models import Collection, CollectionItem
from articles.models import Article
from home.models import HomePage
from media_library.models import Image, ImageRendition
from navigation.models import MenuItem


def hyphenated_name(name):
    path = PurePosixPath(name)
    match = re.match(r"^([0-9a-f]{32})(?=[_.])", path.name)
    if not match:
        return name
    return str(path.with_name(str(UUID(match[1])) + path.name[32:]))


class Command(BaseCommand):
    help = "Add UUID hyphens to existing image files and update their local references."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        # Copy first, commit references second, remove old files last. File bytes and
        # object IDs stay unchanged; a failed database update leaves originals intact.
        storage = Image._meta.get_field("file").storage
        names = set(Image.objects.values_list("file", flat=True))
        names.update(ImageRendition.objects.values_list("file", flat=True))
        names.update(ImageRendition.objects.values_list("source_name", flat=True))
        mapping = {name: hyphenated_name(name) for name in names}
        mapping = {old: new for old, new in mapping.items() if old != new}
        for old, new in sorted(mapping.items()):
            if not storage.exists(old):
                raise CommandError(f"Missing source file: {old}")
            if storage.exists(new):
                raise CommandError(f"Destination already exists: {new}")
            self.stdout.write(f"{old} -> {new}")
        if not options["apply"]:
            self.stdout.write(f"Files to rename: {len(mapping)}. Database unchanged.")
            return
        if not mapping:
            self.stdout.write("Nothing to rename.")
            return

        urls = {storage.url(old): storage.url(new) for old, new in mapping.items()}
        pattern = re.compile(
            "(?:" + "|".join(re.escape(url) for url in urls) + r")(?![\w.-])"
        )
        copied = []
        try:
            for old, new in mapping.items():
                with storage.open(old, "rb") as source:
                    saved = storage.save(new, source)
                copied.append(saved)
                if saved != new:
                    raise CommandError(f"Destination changed during copy: {new}")
            with transaction.atomic():
                for old, new in mapping.items():
                    Image.objects.filter(file=old).update(file=new)
                    ImageRendition.objects.filter(file=old).update(file=new)
                    ImageRendition.objects.filter(source_name=old).update(
                        source_name=new
                    )
                # Update only live site content. Drupal URLs and metadata are an
                # immutable record of the source site, not local file references.
                for model, fields in (
                    (Article, ("content",)),
                    (HomePage, ("content",)),
                    (Collection, ("introduction",)),
                    (CollectionItem, ("annotation",)),
                    (MenuItem, ("url",)),
                ):
                    for row in model.objects.select_for_update().all():
                        changes = {}
                        for field in fields:
                            old = getattr(row, field)
                            new = pattern.sub(lambda match: urls[match[0]], old)
                            if old != new:
                                changes[field] = new
                        if changes:
                            model.objects.filter(pk=row.pk).update(**changes)
        except Exception:
            for name in copied:
                storage.delete(name)
            raise

        for old in mapping:
            storage.delete(old)
        self.stdout.write(
            self.style.SUCCESS(f"Renamed {len(mapping)} files; references updated.")
        )
