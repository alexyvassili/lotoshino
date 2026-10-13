from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.template import Context
from django.test import RequestFactory, TestCase
from django.urls import reverse

from article_collections.models import Collection
from articles.models import Article
from home.models import HomePage

from .forms import MenuItemForm
from .models import Menu, MenuItem, validate_menu_url
from .templatetags.navigation_tags import site_menus


class MenuTests(TestCase):
    def setUp(self):
        self.article = Article.objects.create(title="Article", content="<p>Text</p>")
        self.collection = Collection.objects.create(title="History", slug="history")
        self.user = get_user_model().objects.create_superuser(username="menu-editor")
        self.client.force_login(self.user)

    def form(self, **kwargs):
        return MenuItemForm(
            {
                "title": "Link",
                "page": "",
                "url": "",
                "is_visible": True,
                "position": 0,
                **kwargs,
            }
        )

    def menus(self, path="/"):
        return site_menus(Context({"request": RequestFactory().get(path)}))

    def test_two_fixed_menus_and_automatic_home_link(self):
        self.assertEqual(
            list(Menu.objects.values_list("code", flat=True)), ["main", "top"]
        )
        self.assertEqual(
            [str(menu) for menu in Menu.objects.all()], ["Главное", "Верхнее"]
        )
        self.assertEqual(self.menus()["main"], [])
        self.assertContains(
            self.client.get(self.article.get_absolute_url()),
            ">Главная страница</a>",
            count=1,
        )
        self.assertNotContains(self.client.get("/"), ">Главная страница</a>")
        self.assertEqual(
            self.client.get(reverse("admin:navigation_menu_add")).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("admin:navigation_menu_delete", args=["main"])
            ).status_code,
            403,
        )
        self.assertTrue(MenuItem().is_visible)

    def test_page_choice_and_manual_url_are_mutually_exclusive(self):
        targets = [
            f"home_page:{HomePage.objects.get().pk}",
            f"article:{self.article.pk}",
            f"collection:{self.collection.pk}",
        ]
        for target in targets:
            form = self.form(page=target)
            self.assertTrue(form.is_valid(), form.errors)
            item = form.save(commit=False)
            self.assertTrue(item.get_destination().startswith("/"))
        for data in (
            {},
            {"page": targets[0], "url": "/another/"},
            {"page": "article:99999"},
        ):
            form = self.form(**data)
            self.assertFalse(form.is_valid())
        for url in (
            "/history/",
            "https://example.org/page?q=one#part",
            "http://example.org/",
        ):
            form = self.form(url=url)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.save(commit=False).get_destination(), url)

    def test_unsafe_urls_rejected_in_form_and_rendering(self):
        for url in (
            "javascript:alert(1)",
            "data:text/html,bad",
            "//example.org/",
            "/\\example.org",
            "https://example.org/ bad",
            "/bad\npath",
        ):
            with self.subTest(url=url):
                self.assertFalse(self.form(url=url).is_valid())
                with self.assertRaises(ValidationError):
                    validate_menu_url(url)
                # Defense for old or programmatically created records, too.
                self.assertIsNone(MenuItem(url=url).get_destination())

    def test_order_visibility_drafts_and_renamed_pages(self):
        MenuItem.objects.create(
            menu_id="top", title="Last", article=self.article, position=9
        )
        MenuItem.objects.create(
            menu_id="top", title="First", collection=self.collection, position=1
        )
        MenuItem.objects.create(
            menu_id="top", title="Hidden", url="/", is_visible=False
        )
        self.assertEqual(
            [item["title"] for item in self.menus()["top"]], ["First", "Last"]
        )
        self.article.slug = "new-address"
        self.article.save()
        self.assertEqual(self.menus()["top"][1]["url"], "/articles/new-address/")
        self.article.is_published = False
        self.article.save()
        self.assertEqual([item["title"] for item in self.menus()["top"]], ["First"])
        self.collection.is_published = False
        self.collection.save()
        self.assertEqual(self.menus()["top"], [])

    def test_deleting_target_hides_link_without_deleting_menu_item(self):
        item = MenuItem.objects.create(
            menu_id="top", title="Target", article=self.article
        )
        self.article.delete()
        item.refresh_from_db()
        self.assertIsNone(item.article_id)
        self.assertEqual(self.menus()["top"], [])

    def test_switching_destination_clears_old_page(self):
        item = MenuItem.objects.create(menu_id="top", title="Old", article=self.article)
        form = MenuItemForm(
            {
                "title": "New",
                "page": f"collection:{self.collection.pk}",
                "url": "",
                "is_visible": True,
                "position": 0,
            },
            instance=item,
        )
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertIsNone(item.article_id)
        self.assertEqual(item.collection_id, self.collection.pk)
        form = MenuItemForm(
            {
                "title": "External",
                "page": "",
                "url": "https://example.org/",
                "is_visible": True,
                "position": 0,
            },
            instance=item,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().collection_id)

    def test_admin_saves_order_and_checkbox_and_protects_access(self):
        url = reverse("admin:navigation_menu_change", args=["top"])
        data = {
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        }
        for i in range(2):
            data.update(
                {
                    f"items-{i}-title": f"Item {i}",
                    f"items-{i}-url": f"/page-{i}/",
                    f"items-{i}-position": 1 - i,
                }
            )
        data["items-1-is_visible"] = "on"
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(
                MenuItem.objects.filter(menu_id="top").values_list("title", flat=True)
            ),
            ["Item 1", "Item 0"],
        )
        self.assertEqual([item["title"] for item in self.menus()["top"]], ["Item 1"])
        response = self.client.get(url)
        self.assertContains(response, "Показывать в меню")
        self.assertContains(response, "Главная страница")
        self.assertContains(response, "Подборки статей")
        self.client.force_login(
            get_user_model().objects.create_user(username="limited", is_staff=True)
        )
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_public_templates_and_one_query(self):
        MenuItem.objects.create(
            menu_id="top", title="<b>History</b>", collection=self.collection
        )
        MenuItem.objects.create(
            menu_id="main", title="Article navigation", article=self.article, position=1
        )
        self.client.logout()
        response = self.client.get(self.article.get_absolute_url())
        self.assertContains(response, 'aria-label="Верхнее меню"')
        self.assertContains(response, "&lt;b&gt;History&lt;/b&gt;")
        self.assertContains(response, 'aria-current="page">Article navigation')
        with self.assertNumQueries(1):
            self.assertEqual(len(self.menus()["main"]), 1)
