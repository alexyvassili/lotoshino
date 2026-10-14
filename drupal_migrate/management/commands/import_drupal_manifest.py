import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from drupal_migrate.importer import import_article, import_collection, verify_file


class Command(BaseCommand):
    help = "Import a reviewed Drupal manifest. Without --apply, validate files only."

    def add_arguments(self, parser):
        parser.add_argument("manifest", type=Path)
        parser.add_argument("--web-root", type=Path, required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            manifest = json.loads(options["manifest"].read_text())
            pages = [*manifest["articles"]]
            if manifest.get("collection"):
                pages.append(
                    {
                        "images": {
                            str(i): item["image"]
                            for i, item in enumerate(manifest["collection"]["items"])
                            if item.get("image")
                        }
                    }
                )
            for page in pages:
                for spec in page.get("images", {}).values():
                    verify_file(spec, options["web_root"])
                    if spec.get("display"):
                        verify_file(spec["display"], options["web_root"], variant=True)
            if not options["apply"]:
                self.stdout.write("Source files verified; database unchanged.")
                return
            for page in manifest["articles"]:
                article, created = import_article(page, options["web_root"])
                self.stdout.write(
                    f"{'Created' if created else 'Reused'}: {article.get_absolute_url()}"
                )
            if manifest.get("collection"):
                collection, created = import_collection(
                    manifest["collection"], options["web_root"]
                )
                self.stdout.write(
                    f"{'Created' if created else 'Reused'}: {collection.get_absolute_url()}"
                )
        except (ValueError, KeyError, OSError) as exc:
            raise CommandError(str(exc)) from exc
