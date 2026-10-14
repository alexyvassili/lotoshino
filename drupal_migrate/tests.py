from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from articles.models import Article
from media_library.models import Image

from .models import (
    DrupalMigrateArticleMap,
    DrupalMigrateArticles,
    DrupalMigrateFileManaged,
    DrupalMigrateFileMap,
    DrupalMigrateURL,
)


class MigrationModelsTests(TestCase):
    def source(self):
        return DrupalMigrateArticles.objects.create(
            drupal_migrate_node_id=121,
            drupal_migrate_title="Старая статья",
            drupal_migrate_status=True,
            drupal_migrate_created=1_300_000_000,
            drupal_migrate_changed=1_400_000_000,
        )

    def file(self):
        return DrupalMigrateFileManaged.objects.create(
            drupal_migrate_filename="old.jpg",
            drupal_migrate_filemime="image/jpeg",
            drupal_migrate_filesize=1024,
        )

    def test_mapping_keeps_old_dates_separate_and_protects_article(self):
        source = self.source()
        article = Article.objects.create(title="Новая статья", content="<p>Текст</p>")
        DrupalMigrateArticleMap.objects.create(drupal_article=source, article=article)
        self.assertGreater(
            article.created_at.timestamp(), source.drupal_migrate_changed
        )
        with self.assertRaises(ProtectedError):
            article.delete()
        article.title = "Изменённый заголовок"
        article.save()
        source.refresh_from_db()
        self.assertEqual(source.drupal_migrate_title, "Старая статья")

    def test_file_map_requires_exactly_one_target(self):
        source = self.file()
        with self.assertRaises(IntegrityError), transaction.atomic():
            DrupalMigrateFileMap.objects.create(drupal_file=source)
        image = Image.objects.create(title="Картинка", file="images/example.jpg")
        DrupalMigrateFileMap.objects.create(drupal_file=source, image=image)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DrupalMigrateFileMap.objects.create(drupal_file=source, image=image)

    def test_url_has_unique_path_and_exactly_one_source(self):
        article, file = self.source(), self.file()
        for values in ({}, {"drupal_article": article, "drupal_file": file}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                DrupalMigrateURL.objects.create(url="/node/121", **values)
        DrupalMigrateURL.objects.create(url="/node/121", drupal_article=article)
        with self.assertRaises(IntegrityError), transaction.atomic():
            DrupalMigrateURL.objects.create(url="/node/121", drupal_file=file)

    def test_missing_fid_is_null_not_an_invented_identifier(self):
        first, second = self.file(), self.file()
        self.assertIsNone(first.drupal_migrate_file_id)
        self.assertIsNone(second.drupal_migrate_timestamp)
        first.drupal_migrate_file_id = 42
        first.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.drupal_migrate_file_id = 42
            second.save()


class ManifestImportTests(TestCase):
    def setUp(self):
        import tempfile
        from hashlib import sha256
        from pathlib import Path

        from PIL import Image as PillowImage

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.media = self.root / "media"
        self.settings_override = self.settings(MEDIA_ROOT=self.media)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.original = self.root / "source.jpg"
        PillowImage.new("RGB", (800, 544), "navy").save(self.original)
        self.thumbnail = self.root / "small.jpg"
        PillowImage.new("RGB", (300, 204), "green").save(self.thumbnail)
        self.page = {
            "nid": 119,
            "title": "История",
            "status": 1,
            "created": 1_300_000_000,
            "changed": 1_400_000_000,
            "slug": "history-test",
            "urls": ["/node/119", "/history-test"],
            "html": '{{image:one}}<p>Текст</p><p><a href="{{full:one}}" data-illustration="true">Иллюстрация</a></p>',
            "images": {
                "one": {
                    "path": "/source.jpg",
                    "title": "Храм",
                    "alt": "Старый храм",
                    "sha256": sha256(self.original.read_bytes()).hexdigest(),
                    "allow_unmanaged": True,
                    "approved_as_master": True,
                    "display_size": [300, 204],
                    "display": {
                        "path": "/small.jpg",
                        "sha256": sha256(self.thumbnail.read_bytes()).hexdigest(),
                        "allow_unmanaged": True,
                        "approved_variant": True,
                    },
                    "usages": [
                        {
                            "field": "body:image",
                            "position": 0,
                            "alt": "Старый храм",
                            "title": "Старый title",
                            "width": 300,
                            "height": 204,
                            "source_url": "/small.jpg",
                        }
                    ],
                }
            },
        }

    def test_document_import_preserves_bytes_and_metadata_and_reuses_mapping(self):
        from hashlib import sha256

        from document_library.models import Document

        from .importer import file_bytes, import_article
        from .models import DrupalMigrateFileUsage

        data = b"%PDF-1.4\nArchive leaflet\n%%EOF"
        (self.root / "leaflet.pdf").write_bytes(data)
        page = self.page | {
            "images": {},
            "html": '<p><a href="{{document:leaflet}}">Download</a></p>',
            "documents": {
                "leaflet": {
                    "path": "/leaflet.pdf",
                    "title": "Leaflet",
                    "sha256": sha256(data).hexdigest(),
                    "filemime": "application/pdf",
                    "approved_as_master": True,
                    "allow_unmanaged": True,
                    "usages": [
                        {
                            "field": "body:document",
                            "position": 0,
                            "source_url": "/leaflet.pdf",
                            "alt": "",
                            "title": "",
                            "width": None,
                            "height": None,
                        }
                    ],
                }
            },
        }
        article, created = import_article(page, self.root)
        self.assertTrue(created)
        document = Document.objects.get()
        self.assertEqual(file_bytes(document.file), data)
        self.assertIn(document.get_link_url(), article.content)
        self.assertEqual(document.file_format, "PDF")
        self.assertEqual(document.original_name, "leaflet.pdf")
        metadata = DrupalMigrateFileManaged.objects.get()
        self.assertIsNone(metadata.drupal_migrate_file_id)
        self.assertIsNone(metadata.drupal_migrate_width)
        self.assertEqual(metadata.file_map.document, document)
        page.update(nid=120, slug="another", urls=["/node/120"])
        import_article(page, self.root)
        self.assertEqual(Document.objects.count(), 1)
        self.assertEqual(DrupalMigrateFileManaged.objects.count(), 1)
        self.assertEqual(DrupalMigrateFileUsage.objects.count(), 2)
        response = self.client.get(document.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), data)

    def test_document_with_wrong_signature_leaves_no_article_or_files(self):
        from hashlib import sha256

        from django.core.exceptions import ValidationError

        from document_library.models import Document

        from .importer import import_article

        data = b"MZ this is not a PDF"
        (self.root / "bad.pdf").write_bytes(data)
        page = self.page | {
            "html": '<a href="{{document:bad}}">Bad</a>',
            "images": {},
            "documents": {
                "bad": {
                    "path": "/bad.pdf",
                    "title": "Bad",
                    "sha256": sha256(data).hexdigest(),
                    "filemime": "application/pdf",
                    "approved_as_master": True,
                    "allow_unmanaged": True,
                    "usages": [],
                }
            },
        }
        with self.assertRaises(ValidationError):
            import_article(page, self.root)
        self.assertFalse(Document.objects.exists())
        self.assertFalse(Article.objects.exists())
        self.assertFalse(DrupalMigrateArticles.objects.exists())

    def test_import_copies_archive_versions_verbatim_and_records_each_file(self):
        from uuid import UUID

        from .importer import import_article
        from .models import DrupalMigrateFileUsage

        article, created = import_article(self.page, self.root)
        self.assertTrue(created)
        self.assertIn('width="300" height="204"', article.content)
        self.assertIn('data-viewer="true"', article.content)
        self.assertNotIn("{{", article.content)
        image = Image.objects.get()
        self.assertEqual((image.file.width, image.file.height), (800, 544))
        version = image.renditions.get(kind="imported")
        self.assertEqual(version.width, 300)
        stem = image.file.name.split("/")[-1].split(".")[0]
        self.assertEqual(stem, str(UUID(stem)))
        self.assertEqual(version.file.name, f"images/{stem}_300x204.jpg")
        with image.file.open("rb") as file:
            self.assertEqual(file.read(), self.original.read_bytes())
        with version.file.open("rb") as file:
            self.assertEqual(file.read(), self.thumbnail.read_bytes())
        self.assertEqual(image.renditions.count(), 1)
        self.assertEqual(DrupalMigrateURL.objects.count(), 4)
        usage = DrupalMigrateFileUsage.objects.get()
        self.assertEqual(usage.drupal_migrate_title, "Старый title")
        self.assertEqual(usage.drupal_migrate_source_url, "/small.jpg")
        self.assertEqual(usage.drupal_file.file_map.rendition, version)
        self.assertTrue(DrupalMigrateURL.objects.filter(url="/small.jpg").exists())

    def test_repeat_import_preserves_edits_and_reuses_files_across_articles(self):
        from .importer import import_article

        article, _ = import_article(self.page, self.root)
        article.content = "<p>Редактор изменил текст</p>"
        article.save()
        repeated, created = import_article(self.page, self.root)
        self.assertFalse(created)
        self.assertEqual(repeated.content, article.content)
        self.page.update(nid=123, slug="another", urls=["/node/123"])
        import_article(self.page, self.root)
        self.assertEqual(Article.objects.count(), 2)
        self.assertEqual(Image.objects.count(), 1)
        self.assertEqual(DrupalMigrateFileManaged.objects.count(), 2)

    def test_failure_rolls_back_metadata_and_removes_only_new_files(self):
        from .importer import import_article

        self.media.mkdir()
        existing = self.media / "existing.txt"
        existing.write_text("keep")
        self.page["urls"] = ["https://wrong.example/"]
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            import_article(self.page, self.root)
        self.assertFalse(Article.objects.exists())
        self.assertFalse(Image.objects.exists())
        self.assertFalse(DrupalMigrateArticles.objects.exists())
        self.assertEqual([p for p in self.media.rglob("*") if p.is_file()], [existing])

    def test_collection_reuses_identical_archived_thumbnail_under_another_old_url(self):
        from copy import deepcopy
        from unittest.mock import patch

        from media_library.models import ImageRendition

        from .importer import import_article, import_collection

        import_article(self.page, self.root)
        image_spec = deepcopy(self.page["images"]["one"])
        image_spec["display"]["path"] = "/card.jpg"
        (self.root / "card.jpg").write_bytes(self.thumbnail.read_bytes())
        collection_page = {
            **self.page,
            "nid": 7,
            "slug": "history-collection",
            "urls": ["/node/7"],
            "template_name": "article_collections/layouts/history.html",
            "items": [
                {
                    "nid": 119,
                    "annotation": "Описание",
                    "image": image_spec,
                    "usage": {
                        **image_spec["usages"][0],
                        "field": "collection:image",
                        "source_url": "/card.jpg",
                    },
                }
            ],
        }
        collection, created = import_collection(collection_page, self.root)
        self.assertTrue(created)
        self.assertEqual(Image.objects.count(), 1)
        self.assertEqual(ImageRendition.objects.count(), 1)
        self.assertEqual(DrupalMigrateFileManaged.objects.count(), 3)
        self.assertEqual(len(list(self.media.rglob("*.jpg"))), 2)
        card = collection.items.get()
        self.assertEqual(card.imported_preview.file.read(), self.thumbnail.read_bytes())
        with patch(
            "article_collections.views.article_image_data",
            side_effect=AssertionError("Must not generate sizes"),
        ):
            response = self.client.get(collection.get_absolute_url())
        self.assertContains(response, card.imported_preview.file.url)
        self.assertFalse(import_collection(collection_page, self.root)[1])
        card.image = Image.objects.create(title="Other", file="images/other.jpg")
        card.save()
        self.assertIsNone(card.imported_preview_id)

    def test_failed_image_insert_removes_file_written_before_save(self):
        from unittest.mock import patch

        from .importer import import_article

        with (
            patch.object(Image, "save", side_effect=RuntimeError),
            self.assertRaises(RuntimeError),
        ):
            import_article(self.page, self.root)
        self.assertFalse(DrupalMigrateArticles.objects.exists())
        self.assertEqual(list(self.media.rglob("*.jpg")), [])

    def test_unreviewed_or_changed_files_cannot_be_imported(self):
        from .importer import import_article

        spec = self.page["images"]["one"]
        spec["allow_unmanaged"] = False
        with self.assertRaisesRegex(ValueError, "decision"):
            import_article(self.page, self.root)
        spec["allow_unmanaged"] = True
        spec["approved_as_master"] = False
        with self.assertRaisesRegex(ValueError, "reviewed"):
            import_article(self.page, self.root)
        spec["approved_as_master"] = True
        spec["sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "changed"):
            import_article(self.page, self.root)
        self.assertFalse(DrupalMigrateArticles.objects.exists())
