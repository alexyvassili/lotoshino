from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from articles.models import Article

from .downloads import image_download_urls
from .models import Image, ImageRendition
from .renditions import article_renditions
from .storage import image_storage, physical_image_name
from .tests import uploaded_image


class ImageStorageTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.root = Path(directory.name)

    def test_new_upload_and_renditions_have_flat_urls_and_sharded_files(self):
        image = Image.objects.create(title="Photo", file=uploaded_image((640, 480)))
        versions = article_renditions(image)
        for obj in (image, *versions.values()):
            name = Path(obj.file.name).name
            self.assertEqual(obj.file.name, f"images/{name}")
            self.assertEqual(obj.file.url, f"/media/images/{name}")
            self.assertEqual(
                Path(obj.file.path), self.root / "images" / name[:2] / name
            )
            self.assertTrue(Path(obj.file.path).is_file())
            self.assertFalse((self.root / "images" / name).exists())
        content = f'<img src="{versions["preview"].file.url}">'
        self.assertEqual(
            image_download_urls(content)[versions["preview"].file.url], image.file.url
        )
        self.assertEqual(
            article_renditions(image)["preview"].pk, versions["preview"].pk
        )

    def test_public_image_url_streams_file_without_database_queries_in_production(self):
        image = Image.objects.create(title="Photo", file=uploaded_image())
        for debug in (False, True):
            with (
                self.subTest(debug=debug),
                override_settings(DEBUG=debug),
                self.assertNumQueries(0),
            ):
                response = self.client.get(image.file.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/png")
                with image.file.open("rb") as file:
                    self.assertEqual(b"".join(response.streaming_content), file.read())
                response.close()
                head = self.client.head(image.file.url)
                self.assertEqual(head.status_code, 200)
                self.assertEqual(b"".join(head.streaming_content), b"")
                head.close()
                cached = self.client.get(
                    image.file.url, HTTP_IF_MODIFIED_SINCE=response["Last-Modified"]
                )
                self.assertEqual(cached.status_code, 304)
        self.assertEqual(self.client.post(image.file.url).status_code, 405)

    def test_missing_invalid_and_physical_urls_cannot_expose_files(self):
        image = Image.objects.create(title="Photo", file=uploaded_image())
        for url in (
            "/media/images/01234567-89ab-4def-8123-456789abcdef.jpg",
            "/media/" + physical_image_name(image.file.name),
            "/media/images/../documents/private.pdf",
            "/media/images/anything.txt",
        ):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_collision_preserves_existing_file_and_flat_returned_name(self):
        name = "images/01234567-89ab-4def-8123-456789abcdef_320x240.png"
        first = image_storage.save(name, ContentFile(b"first"))
        second = image_storage.save(name, ContentFile(b"second"))
        self.assertNotEqual(first, second)
        self.assertEqual(len(Path(second).parts), 2)
        for saved, data in ((first, b"first"), (second, b"second")):
            self.assertEqual(Path(image_storage.path(saved)).parent.name, "01")
            with image_storage.open(saved) as file:
                self.assertEqual(file.read(), data)

    def test_thumbnail_used_as_master_does_not_repeat_dimensions_in_new_name(self):
        stem = "01234567-89ab-4def-8123-456789abcdef"
        name = f"images/{stem}_300x205.png"
        image_storage.save(name, uploaded_image((300, 205)))
        image = Image.objects.create(title="Archive thumbnail", file=name)
        for version in article_renditions(image).values():
            self.assertRegex(
                Path(version.file.name).name,
                rf"^{stem}_300x205(?:_[A-Za-z0-9]{{7}})?\.png$",
            )
            self.assertEqual(Path(version.file.path).parent.name, "01")

    def legacy_files(self):
        self.master = "images/01234567-89ab-4def-8123-456789abcdef.png"
        self.preview = "images/01234567-89ab-4def-8123-456789abcdef_320x240.png"
        flat = FileSystemStorage()
        flat.save(self.master, uploaded_image((640, 480)))
        flat.save(self.preview, uploaded_image((320, 240)))
        image = Image.objects.create(title="Old", file=self.master)
        ImageRendition.objects.create(
            image=image,
            source_name=self.master,
            kind="article_preview",
            max_width=320,
            max_height=240,
            width=320,
            height=240,
            file=self.preview,
        )
        self.article = Article.objects.create(
            title="Old article",
            content=f'<img src="/media/{self.preview}" data-full-size="/media/{self.master}">',
        )
        return {
            name: (self.root / name).read_bytes()
            for name in (self.master, self.preview)
        }

    def test_existing_files_move_once_with_identical_bytes_and_unchanged_references(
        self,
    ):
        original = self.legacy_files()
        content = self.article.content
        call_command("shard_image_files", stdout=StringIO())
        self.assertTrue((self.root / self.master).is_file())
        call_command("shard_image_files", apply=True, stdout=StringIO())
        call_command("shard_image_files", apply=True, stdout=StringIO())
        self.article.refresh_from_db()
        self.assertEqual(self.article.content, content)
        self.assertEqual(Image.objects.get().file.name, self.master)
        self.assertEqual(ImageRendition.objects.get().source_name, self.master)
        for name, data in original.items():
            self.assertFalse((self.root / name).exists())
            self.assertEqual((self.root / physical_image_name(name)).read_bytes(), data)
        self.assertEqual(ImageRendition.objects.count(), 1)

    def test_conflicting_destination_never_overwrites_either_file(self):
        original = self.legacy_files()
        image_storage.save(self.master, ContentFile(b"other"))
        with self.assertRaises(CommandError):
            call_command("shard_image_files", apply=True, stdout=StringIO())
        self.assertEqual((self.root / self.master).read_bytes(), original[self.master])
        self.assertEqual(Path(image_storage.path(self.master)).read_bytes(), b"other")

    def test_interrupted_cleanup_can_resume(self):
        original = self.legacy_files()
        image_storage.save(self.master, ContentFile(original[self.master]))
        call_command("shard_image_files", apply=True, stdout=StringIO())
        self.assertFalse((self.root / self.master).exists())
        self.assertEqual(
            Path(image_storage.path(self.master)).read_bytes(), original[self.master]
        )

    def test_failed_move_removes_new_links_and_leaves_all_sources(self):
        import os

        original = self.legacy_files()
        link = os.link
        calls = 0

        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Simulated failure")
            return link(*args)

        with (
            patch(
                "media_library.management.commands.shard_image_files.os.link",
                side_effect=fail_second,
            ),
            self.assertRaises(OSError),
        ):
            call_command("shard_image_files", apply=True, stdout=StringIO())
        for name, data in original.items():
            self.assertEqual((self.root / name).read_bytes(), data)
            self.assertFalse(Path(image_storage.path(name)).exists())
