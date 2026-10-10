from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.forms.models import model_to_dict
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image as PillowImage

from site_settings.models import SiteSettings

from .models import Image, ImageRendition, ImageSettings
from .renditions import article_renditions


def uploaded_image(size=(80, 60)):
    data = BytesIO()
    PillowImage.new("RGB", size, color="green").save(data, "PNG")
    return SimpleUploadedFile("test.png", data.getvalue(), content_type="image/png")


class ImageEditorTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_superuser(
            username="editor-test", password=None
        )
        self.client.force_login(self.user)
        self.upload_url = reverse("admin:article_image_upload")
        self.library_url = reverse("admin:article_image_library")

    def test_upload_and_library(self):
        response = self.client.post(self.upload_url, {"upload": uploaded_image()})
        self.assertEqual(response.status_code, 201)
        image = Image.objects.get()
        versions = article_renditions(image)
        self.assertEqual(response.json()["url"], versions["preview"].file.url)
        self.assertEqual(response.json()["full_url"], versions["full"].file.url)
        self.assertEqual(image.renditions.count(), 2)
        self.assertTrue(image.created_at and image.updated_at)
        with PillowImage.open(image.file.path) as file:
            self.assertEqual(file.size, (80, 60))
        library = self.client.get(self.library_url, {"q": "test"}).json()
        self.assertEqual(library["images"][0]["url"], image.file.url)
        self.assertEqual(
            self.client.get(self.library_url, {"q": "absent"}).json()["images"], []
        )

    def test_invalid_file_and_missing_upload_are_rejected(self):
        response = self.client.post(
            self.upload_url,
            {
                "upload": SimpleUploadedFile(
                    "fake.png", b"<script>bad</script>", content_type="image/png"
                )
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.json()["error"])
        self.assertEqual(self.client.post(self.upload_url).status_code, 400)
        self.assertFalse(Image.objects.exists())

    def test_maximum_dimensions_apply_to_editor_and_library_uploads(self):
        settings = ImageSettings.load()
        settings.max_image_width = 2048
        settings.max_image_height = 2048
        settings.save()
        response = self.client.post(
            self.upload_url,
            {"upload": uploaded_image((3000, 1500))},
        )
        self.assertEqual(response.status_code, 201)
        with PillowImage.open(Image.objects.get().file.path) as image:
            self.assertEqual(image.size, (2048, 1024))
        settings.max_image_height = 2560
        settings.save()
        response = self.client.post(
            reverse("admin:media_library_image_add"),
            {
                "title": "Вертикальная фотография",
                "file": uploaded_image((1500, 3000)),
            },
        )
        self.assertEqual(response.status_code, 302)
        with PillowImage.open(
            Image.objects.get(title="Вертикальная фотография").file.path
        ) as image:
            self.assertEqual(image.size, (1280, 2560))

    def test_site_upload_limit_is_checked_before_resizing(self):
        large_file = uploaded_image().read() + b"\0" * (11 * 1024 * 1024)
        response = self.client.post(
            self.upload_url,
            {"upload": SimpleUploadedFile("large.png", large_file, "image/png")},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("10 МБ", response.json()["error"]["message"])
        self.assertFalse(Image.objects.exists())
        settings = SiteSettings.load()
        settings.max_upload_size_mb = 12
        settings.save()
        response = self.client.post(
            self.upload_url,
            {"upload": SimpleUploadedFile("large.png", large_file, "image/png")},
        )
        self.assertEqual(response.status_code, 201)
        with PillowImage.open(Image.objects.get().file.path) as image:
            self.assertEqual(image.size, (80, 60))

    def test_orientation_is_corrected_before_resizing(self):
        settings = ImageSettings.load()
        settings.max_image_width = 2048
        settings.max_image_height = 2560
        settings.save()
        data = BytesIO()
        image = PillowImage.new("RGB", (3000, 1500), "green")
        exif = image.getexif()
        exif[274] = 6
        image.save(data, "JPEG", exif=exif)
        response = self.client.post(
            self.upload_url,
            {
                "upload": SimpleUploadedFile(
                    "rotated.jpg", data.getvalue(), "image/jpeg"
                )
            },
        )
        self.assertEqual(response.status_code, 201)
        with PillowImage.open(Image.objects.get().file.path) as image:
            self.assertEqual(image.size, (1280, 2560))
            self.assertNotIn(274, image.getexif())

    def test_anonymous_and_staff_without_permissions_cannot_upload(self):
        self.client.logout()
        self.assertEqual(
            self.client.post(self.upload_url, {"upload": uploaded_image()}).status_code,
            302,
        )
        staff = get_user_model().objects.create_user(
            username="staff-test", is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(
            self.client.post(self.upload_url, {"upload": uploaded_image()}).status_code,
            403,
        )
        self.assertEqual(self.client.get(self.library_url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="add_article"))
        self.assertEqual(
            self.client.post(self.upload_url, {"upload": uploaded_image()}).status_code,
            403,
        )
        self.assertFalse(Image.objects.exists())

    def test_upload_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(
            client.post(self.upload_url, {"upload": uploaded_image()}).status_code, 403
        )

    def test_admin_editor_uses_local_assets(self):
        response = self.client.get(reverse("admin:articles_article_add"))
        self.assertContains(response, "vendor/ckeditor5/49.0.0/ckeditor5.umd.js")
        self.assertContains(response, 'data-article-editor="true"')
        self.assertContains(response, self.upload_url)
        self.assertContains(response, self.library_url)

    def test_article_sizes_use_master_and_orientation_without_upscaling(self):
        for size, expected_master, expected_preview, expected_full in (
            ((3000, 1500), (2560, 1280), (320, 160), (1280, 640)),
            ((1500, 3000), (1280, 2560), (180, 360), (720, 1440)),
            ((1000, 1000), (1000, 1000), (240, 240), (960, 960)),
            ((80, 60), (80, 60), (80, 60), (80, 60)),
        ):
            with self.subTest(size=size):
                response = self.client.post(
                    self.upload_url, {"upload": uploaded_image(size)}
                )
                self.assertEqual(response.status_code, 201)
                image = Image.objects.get(pk=response.json()["id"])
                with PillowImage.open(image.file.path) as source:
                    self.assertEqual(source.size, expected_master)
                for kind, expected in (
                    ("preview", expected_preview),
                    ("full", expected_full),
                ):
                    rendition = image.renditions.get(kind=f"article_{kind}")
                    with PillowImage.open(rendition.file.path) as result:
                        self.assertEqual(result.size, expected)
                        self.assertEqual((rendition.width, rendition.height), expected)

    def test_existing_library_image_prepares_only_on_selection_and_reuses_files(self):
        image = Image.objects.create(
            title="Existing", file=uploaded_image((1600, 1200))
        )
        item = self.client.get(self.library_url).json()["images"][0]
        self.assertFalse(image.renditions.exists())
        first = self.client.post(item["prepare_url"])
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.client.post(item["prepare_url"]).json(), first.json())
        self.assertEqual(image.renditions.count(), 2)
        old_files = list(image.renditions.all())
        settings = ImageSettings.load()
        settings.article_preview_width = 200
        settings.save()
        changed = self.client.post(item["prepare_url"]).json()
        self.assertNotEqual(changed["url"], first.json()["url"])
        self.assertEqual(changed["full_url"], first.json()["full_url"])
        self.assertEqual(image.renditions.count(), 3)
        for version in old_files:
            self.assertTrue(version.file.storage.exists(version.file.name))
        response = self.client.get(
            reverse("admin:media_library_image_change", args=[image.pk])
        )
        self.assertContains(response, "Основная версия")
        self.assertContains(response, "Статья — превью", count=4)
        self.assertContains(response, "Статья — полная версия")
        self.assertContains(response, "1600 &times; 1200 px")

    def test_replacing_master_creates_new_versions_and_keeps_existing_links(self):
        image = Image.objects.create(title="Replace", file=uploaded_image((1600, 1200)))
        old = article_renditions(image)
        image.file = uploaded_image((1200, 1600))
        image.save()
        new = article_renditions(image)
        self.assertEqual(image.renditions.count(), 4)
        for kind in ("preview", "full"):
            self.assertNotEqual(old[kind].file.name, new[kind].file.name)
            self.assertTrue(old[kind].file.storage.exists(old[kind].file.name))
            self.assertGreater(new[kind].height, new[kind].width)

    def test_missing_derivative_is_rebuilt_and_missing_master_returns_error(self):
        image = Image.objects.create(title="Missing", file=uploaded_image((1600, 1200)))
        versions = article_renditions(image)
        preview = versions["preview"]
        preview.file.storage.delete(preview.file.name)
        rebuilt = article_renditions(image)["preview"]
        self.assertEqual(preview.pk, rebuilt.pk)
        self.assertTrue(rebuilt.file.storage.exists(rebuilt.file.name))
        image.file.storage.delete(image.file.name)
        response = self.client.post(
            reverse("admin:article_image_prepare", args=[image.pk])
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.json()["error"])

    def test_prepare_requires_post_permissions_and_csrf(self):
        image = Image.objects.create(title="Permissions", file=uploaded_image())
        url = reverse("admin:article_image_prepare", args=[image.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(url).status_code, 403)
        staff = get_user_model().objects.create_user(username="chooser", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="change_article"))
        self.assertEqual(self.client.post(url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="view_image"))
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(
            self.client.post(
                reverse("admin:article_image_prepare", args=[99999])
            ).status_code,
            404,
        )

    def test_jpeg_master_is_saved_at_high_quality(self):
        data = BytesIO()
        PillowImage.new("RGB", (3000, 1500), "green").save(data, "JPEG", quality=98)
        response = self.client.post(
            self.upload_url,
            {"upload": SimpleUploadedFile("photo.jpg", data.getvalue(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 201)
        image = Image.objects.get(pk=response.json()["id"])
        with PillowImage.open(image.file.path) as master:
            self.assertEqual(master.size, (2560, 1280))
            self.assertLessEqual(max(master.quantization[0]), 12)

    def test_exif_orientation_selects_portrait_profile(self):
        data = BytesIO()
        original = PillowImage.new("RGB", (2400, 1200), "green")
        exif = original.getexif()
        exif[274] = 6
        original.save(data, "JPEG", exif=exif)
        response = self.client.post(
            self.upload_url,
            {
                "upload": SimpleUploadedFile(
                    "portrait.jpg", data.getvalue(), "image/jpeg"
                )
            },
        )
        self.assertEqual(response.status_code, 201)
        preview = ImageRendition.objects.get(kind="article_preview")
        self.assertEqual((preview.width, preview.height), (180, 360))


class ImageSettingsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="settings-admin", password=None
        )
        self.client.force_login(user)
        self.list_url = reverse("admin:media_library_imagesettings_changelist")
        self.change_url = reverse("admin:media_library_imagesettings_change", args=[1])

    def test_settings_exist_and_open_from_admin_navigation(self):
        self.assertEqual(ImageSettings.objects.count(), 1)
        response = self.client.get(reverse("admin:media_library_image_changelist"))
        self.assertContains(response, "Настройки изображений")
        self.assertContains(response, self.list_url)
        self.assertRedirects(self.client.get(self.list_url), self.change_url)
        response = self.client.get(self.change_url)
        self.assertContains(response, "Галерея — вертикальные изображения")
        self.assertContains(response, "Статьи — вертикальные изображения")

    def test_admin_saves_settings_and_rejects_invalid_dimensions(self):
        data = model_to_dict(ImageSettings.load())
        data.update(max_image_width=3000, article_preview_width=360)
        response = self.client.post(self.change_url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ImageSettings.load().article_preview_width, 360)
        self.assertEqual(ImageSettings.load().max_image_width, 3000)
        data["article_preview_width"] = 2000
        response = self.client.post(self.change_url, data)
        self.assertContains(response, "Размер превью не должен превышать")
        self.assertEqual(ImageSettings.load().article_preview_width, 360)

    def test_zero_and_excessive_dimensions_are_rejected(self):
        for field, value in (
            ("max_image_width", 0),
            ("gallery_preview_height", 0),
            ("article_portrait_full_height", 10001),
        ):
            with self.subTest(field=field):
                settings = ImageSettings.load()
                setattr(settings, field, value)
                with self.assertRaises(ValidationError) as error:
                    settings.full_clean()
                self.assertIn(field, error.exception.message_dict)

    def test_singleton_cannot_be_added_or_deleted(self):
        self.assertEqual(
            self.client.get(
                reverse("admin:media_library_imagesettings_add")
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("admin:media_library_imagesettings_delete", args=[1]),
                {"post": "yes"},
            ).status_code,
            403,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ImageSettings.objects.create(pk=2)
        self.assertEqual(ImageSettings.objects.count(), 1)

    def test_settings_require_their_own_permissions(self):
        user = get_user_model().objects.create_user(
            username="image-editor", is_staff=True
        )
        user.user_permissions.add(Permission.objects.get(codename="change_image"))
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename="view_imagesettings"))
        self.assertRedirects(self.client.get(self.list_url), self.change_url)
        self.assertEqual(self.client.post(self.change_url, {}).status_code, 403)
