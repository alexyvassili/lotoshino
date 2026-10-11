from inspect import iscoroutinefunction
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from .debug_toolbar import show_toolbar


class AsyncIndexTests(SimpleTestCase):
    async def test_home_uses_async_view(self):
        self.assertTrue(iscoroutinefunction(resolve("/").func))
        response = await self.async_client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Лотошино")

    async def test_home_rejects_post(self):
        response = await self.async_client.post("/")
        self.assertEqual(response.status_code, 405)


@override_settings(DEBUG=True, INTERNAL_IPS=["127.0.0.1", "::1"])
class DebugToolbarAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_user(
            username="toolbar_admin", is_staff=True, is_superuser=True
        )
        cls.staff = get_user_model().objects.create_user(
            username="toolbar_staff", is_staff=True
        )
        cls.member = get_user_model().objects.create_user(username="toolbar_member")

    def test_only_superuser_sees_toolbar_and_can_load_panel(self):
        panel_url = reverse("djdt:render_panel")
        params = {"request_id": "missing", "panel_id": "SQLPanel"}
        for user in (None, self.member, self.staff, self.superuser):
            with self.subTest(user=user):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                response = self.client.get("/")
                expected = user == self.superuser
                self.assertEqual(b'id="djDebug"' in response.content, expected)
                panel = self.client.get(panel_url, params)
                self.assertEqual(panel.status_code, 200 if expected else 404)

    def test_debug_disabled_blocks_superuser(self):
        self.client.force_login(self.superuser)
        with override_settings(DEBUG=False):
            self.assertNotContains(self.client.get("/"), 'id="djDebug"')
            self.assertEqual(
                self.client.get(reverse("djdt:render_panel")).status_code, 404
            )

    def test_nonlocal_address_blocks_superuser(self):
        self.client.force_login(self.superuser)
        self.assertNotContains(
            self.client.get("/", REMOTE_ADDR="192.0.2.1"), 'id="djDebug"'
        )
        self.assertEqual(
            self.client.get(
                reverse("djdt:render_panel"), REMOTE_ADDR="192.0.2.1"
            ).status_code,
            404,
        )

    def test_inactive_superuser_is_denied(self):
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(
            is_authenticated=True, is_active=False, is_superuser=True
        )
        self.assertFalse(show_toolbar(request))
        request.user = AnonymousUser()
        self.assertFalse(show_toolbar(request))

    async def test_toolbar_on_async_home_page(self):
        await self.async_client.aforce_login(self.superuser)
        response = await self.async_client.get("/")
        self.assertContains(response, 'id="djDebug"')
