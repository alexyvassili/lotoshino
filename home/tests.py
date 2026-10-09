from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from .models import HomePage


class HomePageTests(TestCase):
    def test_migration_creates_single_page_with_empty_content(self):
        self.assertEqual(HomePage.objects.count(), 1)
        self.assertEqual(HomePage.objects.get(pk=1).content, "")

    def test_database_rejects_second_page(self):
        for pk in (1, 2):
            with (
                self.subTest(pk=pk),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                HomePage.objects.create(pk=pk, title="Вторая главная")

    def test_partial_save_updates_timestamp(self):
        page = HomePage.objects.get(pk=1)
        previous = page.updated_at
        page.title = "Новый заголовок"
        page.save(update_fields=["title"])
        page.refresh_from_db()
        self.assertGreater(page.updated_at, previous)

    def test_admin_allows_edit_but_not_add_or_delete(self):
        request = RequestFactory().get("/admin/")
        request.user = get_user_model()(
            is_active=True, is_staff=True, is_superuser=True
        )
        model_admin = admin.site._registry[HomePage]
        page = HomePage.objects.get(pk=1)
        self.assertTrue(model_admin.has_change_permission(request, page))
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request, page))
