from inspect import iscoroutinefunction

from django.test import SimpleTestCase
from django.urls import resolve


class AsyncIndexTests(SimpleTestCase):
    async def test_home_uses_async_view(self):
        self.assertTrue(iscoroutinefunction(resolve("/").func))
        response = await self.async_client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Лотошино")

    async def test_home_rejects_post(self):
        response = await self.async_client.post("/")
        self.assertEqual(response.status_code, 405)
