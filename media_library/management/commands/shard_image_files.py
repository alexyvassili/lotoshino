"""Move existing files; logical database names and public URLs do not change."""

import os
from hashlib import file_digest
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from media_library.models import Image, ImageRendition
from media_library.storage import IMAGE_FILENAME, image_storage, physical_image_name


def digest(path):
    with path.open("rb") as file:
        return file_digest(file, "sha256").digest()


class Command(BaseCommand):
    help = "Move images into UUID-prefix subdirectories. Preview unless --apply is set."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        root = Path(image_storage.location)
        names = set(Image.objects.values_list("file", flat=True))
        names.update(ImageRendition.objects.values_list("file", flat=True))
        names.update(ImageRendition.objects.values_list("source_name", flat=True))
        # Include leftover UUID files, but never touch archives or other media types.
        names.update(
            f"images/{path.name}"
            for path in (root / "images").glob("*")
            if path.is_file() and IMAGE_FILENAME.fullmatch(path.name)
        )
        moves = []
        for name in sorted(names):
            destination = physical_image_name(name)
            if destination == name:
                continue
            old, new = root / name, root / destination
            if not old.is_file():
                if new.is_file():
                    continue
                raise CommandError(f"Missing image: {name}")
            if new.exists() and (not new.is_file() or digest(old) != digest(new)):
                raise CommandError(f"Destination differs: {destination}")
            moves.append((old, new))
            self.stdout.write(f"{name} -> {destination}")
        if not options["apply"]:
            self.stdout.write(f"Files to move: {len(moves)}. No changes made.")
            return

        created = []
        try:
            for old, new in moves:
                new.parent.mkdir(parents=True, exist_ok=True)
                if new.exists():
                    # Recheck before removing a source after an interrupted run.
                    if digest(old) != digest(new):
                        raise CommandError(f"Destination changed: {new.name}")
                    continue
                # Exclusive creation on the same filesystem; bytes and timestamps
                # are preserved. Never overwrite a file created by another process.
                os.link(old, new)
                created.append(new)
        except Exception:
            for path in created:
                path.unlink()
            raise
        # Every destination is ready. An interrupted cleanup can safely be resumed.
        for old, _ in moves:
            old.unlink()
        self.stdout.write(
            self.style.SUCCESS(f"Moved {len(moves)} files. URLs unchanged.")
        )
