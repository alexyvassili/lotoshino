from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.test import TestCase, override_settings
from django.urls import path, reverse

from .models import SiteSettings
from .uploads import FileSizeLimitUploadHandler


def upload_probe(request):
    return JsonResponse(
        {"sizes": [file.size for file in request.FILES.getlist("files")]}
    )


urlpatterns = [path("upload/", upload_probe)]


class SiteSettingsAdminTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(
            username="site-admin", password=None
        )
        self.client.force_login(user)
        self.list_url = reverse("admin:site_settings_sitesettings_changelist")
        self.change_url = reverse("admin:site_settings_sitesettings_change", args=[1])

    def test_site_section_and_single_settings_form(self):
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.load().max_upload_size_mb, 10)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Сайт")
        self.assertContains(response, self.list_url)
        self.assertRedirects(self.client.get(self.list_url), self.change_url)
        response = self.client.get(self.change_url)
        self.assertContains(response, 'name="max_upload_size_mb"')
        self.assertNotContains(response, 'name="max_image_width"')
        self.assertNotContains(response, 'name="_addanother"')

    def test_setting_can_be_changed_and_zero_is_rejected(self):
        response = self.client.post(self.change_url, {"max_upload_size_mb": 20})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SiteSettings.load().max_upload_size_mb, 20)
        response = self.client.post(self.change_url, {"max_upload_size_mb": 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteSettings.load().max_upload_size_mb, 20)
        response = self.client.get(reverse("admin:media_library_image_add"))
        self.assertContains(response, 'name="site-upload-limit-mb" content="20"')

    def test_only_authorized_users_can_change_settings(self):
        user = get_user_model().objects.create_user(
            username="site-reader", is_staff=True
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename="view_sitesettings"))
        self.assertRedirects(self.client.get(self.list_url), self.change_url)
        self.assertEqual(
            self.client.post(self.change_url, {"max_upload_size_mb": 50}).status_code,
            403,
        )

    def test_settings_cannot_be_added_or_deleted(self):
        self.assertEqual(
            self.client.get(
                reverse("admin:site_settings_sitesettings_add")
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("admin:site_settings_sitesettings_delete", args=[1]),
                {"post": "yes"},
            ).status_code,
            403,
        )
        with self.assertRaises(ValidationError):
            SiteSettings(pk=2).full_clean()


@override_settings(ROOT_URLCONF=__name__)
class UploadLimitTests(TestCase):
    def setUp(self):
        settings = SiteSettings.load()
        settings.max_upload_size_mb = 1
        settings.save()

    def file(self, size, name="document.pdf"):
        return SimpleUploadedFile(name, b"x" * size, "application/octet-stream")

    def test_exact_limit_is_allowed_and_larger_documents_are_rejected(self):
        limit = 1024 * 1024
        response = self.client.post("/upload/", {"files": self.file(limit)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sizes"], [limit])
        response = self.client.post(
            "/upload/", {"files": self.file(limit + 1)}, HTTP_ACCEPT="application/json"
        )
        self.assertEqual(response.status_code, 413)
        self.assertIn("1 МБ", response.json()["error"]["message"])

    def test_limit_applies_to_each_file_and_rejects_entire_request(self):
        size = 600 * 1024
        response = self.client.post(
            "/upload/", {"files": [self.file(size), self.file(size)]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sizes"], [size, size])
        response = self.client.post(
            "/upload/", {"files": [self.file(100), self.file(1024 * 1024 + 1)]}
        )
        self.assertContains(
            response, "Файлы из этого запроса не сохранены.", status_code=413
        )

    def test_updated_setting_takes_effect_on_next_request(self):
        size = 1024 * 1024 + 1
        self.assertEqual(
            self.client.post("/upload/", {"files": self.file(size)}).status_code, 413
        )
        settings = SiteSettings.load()
        settings.max_upload_size_mb = 2
        settings.save()
        self.assertEqual(
            self.client.post("/upload/", {"files": self.file(size)}).status_code, 200
        )

    def test_handler_counts_chunks_without_trusting_content_length(self):
        from django.core.files.uploadhandler import StopUpload

        handler = FileSizeLimitUploadHandler(None, max_bytes=10)
        handler.new_file("file", "document.pdf", "application/pdf", 1)
        self.assertEqual(handler.receive_data_chunk(b"a" * 6, 0), b"a" * 6)
        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b"a" * 5, 6)
        self.assertTrue(handler.exceeded)
