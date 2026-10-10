from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image as PillowImage

from .models import Image


def uploaded_image():
    data = BytesIO()
    PillowImage.new("RGB", (80, 60), color="green").save(data, "PNG")
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
        self.assertEqual(response.json()["url"], image.file.url)
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
