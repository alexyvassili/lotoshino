from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from articles.links import linked_site_pages
from articles.models import Article
from media_library.models import Image
from media_library.tests import uploaded_image
from media_library.usage import attach_image_pages
from site_settings.models import SiteSettings

from .forms import CollectionItemForm
from .images import article_images
from .layouts import DEFAULT_TEMPLATE, collection_template_choices
from .models import Collection, CollectionItem


class CollectionTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = get_user_model().objects.create_superuser(
            username="collections-test"
        )
        self.client.force_login(self.user)
        self.article = Article.objects.create(title="Article", content="<p>Text</p>")
        self.collection = Collection.objects.create(title="History", slug="history")
        self.picker = reverse("admin:collection_image_picker")
        self.upload = reverse("admin:collection_image_upload")

    def item(self, article=None, **kwargs):
        return CollectionItem.objects.create(
            collection=self.collection,
            article=article or self.article,
            annotation="Annotation",
            **kwargs,
        )

    def test_public_order_titles_escaping_and_drafts(self):
        self.item(position=2, title="Custom heading")
        second = Article.objects.create(title="Second", content="")
        self.item(second, position=1, link_text="More details")
        draft = Article.objects.create(title="Secret", content="", is_published=False)
        self.item(draft)
        self.collection.introduction = "<script>bad()</script>"
        self.collection.save()
        response = Client().get("/history/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertLess(html.index("Second"), html.index("Custom heading"))
        self.assertContains(response, "More details")
        self.assertContains(response, "Читать далее")
        self.assertNotContains(response, "Secret")
        self.assertContains(response, "&lt;script&gt;bad()&lt;/script&gt;")
        self.collection.is_published = False
        self.collection.save()
        self.assertEqual(self.client.get("/history/").status_code, 404)
        self.assertEqual(Client().get("/history/").status_code, 404)

    def test_route_and_reserved_addresses(self):
        self.assertRedirects(self.client.get("/history"), "/history/", status_code=301)
        for slug in ("admin", "articles", "documents", "media", "static", "__debug__"):
            with self.subTest(slug=slug), self.assertRaises(ValidationError):
                Collection(title="Invalid", slug=slug).full_clean()
        self.assertEqual(self.client.get("/does-not-exist/").status_code, 404)

    def test_invalid_collection_form_shows_errors(self):
        for slug in ("/invalid/address/", "адрес"):
            response = self.client.post(
                reverse("admin:article_collections_collection_add"),
                {
                    "title": "Invalid",
                    "slug": slug,
                    "items-TOTAL_FORMS": "0",
                    "items-INITIAL_FORMS": "0",
                    "items-MIN_NUM_FORMS": "0",
                    "items-MAX_NUM_FORMS": "1000",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["adminform"].form.errors)

    def test_admin_generates_collection_url_from_title(self):
        response = self.client.post(
            reverse("admin:article_collections_collection_add"),
            {
                "title": "История благочиния",
                "slug": "",
                "template_name": DEFAULT_TEMPLATE,
                "is_published": "on",
                "items-TOTAL_FORMS": "0",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(response.status_code, 302)
        collection = Collection.objects.get(title="История благочиния")
        self.assertEqual(collection.slug, "istoriya-blagochiniya")
        self.assertEqual(collection.get_absolute_url(), "/istoriya-blagochiniya/")
        self.assertEqual(
            self.client.get(collection.get_absolute_url()).status_code, 200
        )

    def test_generated_urls_are_unique_and_skip_reserved_addresses(self):
        for title in ("История благочиния", "Admin", "Я" * 255, "!!!"):
            with self.subTest(title=title):
                first = Collection.objects.create(title=title)
                second = Collection.objects.create(title=title)
                self.assertNotEqual(first.slug, second.slug)
                self.assertLessEqual(len(second.slug), 100)
                self.assertRegex(first.slug, r"^[a-z0-9_-]+$")
                self.assertFalse(Collection.is_reserved_slug(first.slug))
                self.assertFalse(Collection.is_reserved_slug(second.slug))
                first.full_clean()
                second.full_clean()
        self.assertTrue(Collection.objects.filter(slug="admin-2").exists())

    def test_template_selection_on_creation_and_readonly_after_save(self):
        add_url = reverse("admin:article_collections_collection_add")
        self.assertContains(self.client.get(add_url), 'name="template_name"')
        compact = "article_collections/layouts/compact.html"
        data = {
            "title": "Compact collection",
            "slug": "compact-test",
            "template_name": compact,
            "is_published": "on",
            "items-TOTAL_FORMS": "0",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        }
        self.assertEqual(self.client.post(add_url, data).status_code, 302)
        collection = Collection.objects.get(slug="compact-test")
        self.assertEqual(collection.template_name, compact)
        change_url = reverse(
            "admin:article_collections_collection_change", args=[collection.pk]
        )
        response = self.client.get(change_url)
        self.assertContains(response, compact)
        self.assertNotContains(response, 'name="template_name"')
        # A forged POST must not change the immutable template either.
        data.update(title="Renamed", template_name=DEFAULT_TEMPLATE)
        self.assertEqual(self.client.post(change_url, data).status_code, 302)
        collection.refresh_from_db()
        self.assertEqual(collection.title, "Renamed")
        self.assertEqual(collection.template_name, compact)
        self.assertContains(
            self.client.get(reverse("admin:article_collections_collection_changelist")),
            compact,
        )

    def test_templates_render_same_content_with_different_layouts(self):
        self.item()
        compact = Collection.objects.create(
            title="Compact", template_name="article_collections/layouts/compact.html"
        )
        CollectionItem.objects.create(
            collection=compact, article=self.article, annotation="Shared article"
        )
        draft = Article.objects.create(title="Secret article", is_published=False)
        CollectionItem.objects.create(collection=compact, article=draft, annotation="")
        response = self.client.get(self.collection.get_absolute_url())
        self.assertTemplateUsed(response, DEFAULT_TEMPLATE)
        self.assertContains(response, 'class="collection-entry"')
        response = self.client.get(compact.get_absolute_url())
        self.assertTemplateUsed(response, compact.template_name)
        self.assertContains(response, 'class="collection-compact-list"')
        self.assertContains(response, self.article.get_absolute_url())
        self.assertContains(response, "Shared article")
        self.assertNotContains(response, "Secret article")

    def test_model_rejects_template_changes_and_arbitrary_template_paths(self):
        self.collection.template_name = "article_collections/layouts/compact.html"
        with self.assertRaisesMessage(ValidationError, "Шаблон нельзя изменить"):
            self.collection.full_clean()
        with self.assertRaisesMessage(ValidationError, "Шаблон нельзя изменить"):
            self.collection.save(update_fields=["template_name"])
        self.collection.refresh_from_db()
        self.assertEqual(self.collection.template_name, DEFAULT_TEMPLATE)
        for path in ("admin/base.html", "../detail.html", "/tmp/template.html"):
            with self.subTest(path=path), self.assertRaises(ValidationError):
                Collection.objects.create(title="Invalid", template_name=path)

    def test_new_layout_files_are_available_for_selection(self):
        with TemporaryDirectory() as directory:
            Path(directory, "custom.html").write_text("Custom template")
            Path(directory, "notes.txt").write_text("Not a template")
            with patch("article_collections.layouts.LAYOUT_DIRECTORY", Path(directory)):
                self.assertEqual(
                    collection_template_choices(),
                    [
                        (DEFAULT_TEMPLATE, "Стандартный — изображение и аннотация"),
                        ("article_collections/layouts/custom.html", "custom"),
                    ],
                )
                response = self.client.get(
                    reverse("admin:article_collections_collection_add")
                )
                self.assertContains(response, "article_collections/layouts/custom.html")

    def test_renaming_preserves_url_and_clearing_regenerates(self):
        collection = Collection.objects.create(title="История благочиния")
        collection.title = "История храмов"
        collection.save()
        self.assertEqual(collection.slug, "istoriya-blagochiniya")
        collection.slug = ""
        collection.save(update_fields=["slug"])
        collection.refresh_from_db()
        self.assertEqual(collection.slug, "istoriya-hramov")
        collection.slug = "custom-history"
        collection.save()
        self.assertEqual(collection.slug, "custom-history")

    def test_title_fallback_custom_override_and_duplicate(self):
        data = {
            "collection": self.collection.pk,
            "article": self.article.pk,
            "title": "",
            "annotation": "Summary",
            "link_text": "Читать далее",
            "position": 0,
        }
        form = CollectionItemForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertEqual(item.title, self.article.title)
        form = CollectionItemForm({**data, "title": "Override"}, instance=item)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().title, "Override")
        self.assertFalse(CollectionItemForm(data).is_valid())
        self.collection.delete()
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())

    def test_admin_deletion_preserves_articles_images_and_other_collections(self):
        image = Image.objects.create(title="Cover", file="images/cover.png")
        other_item = self.item(image=image)
        original_content = self.article.content
        for bulk in (False, True):
            with self.subTest(bulk=bulk):
                collection = Collection.objects.create(title="To delete")
                item = CollectionItem.objects.create(
                    collection=collection,
                    article=self.article,
                    image=image,
                    annotation="Only this card is deleted",
                )
                if bulk:
                    url = reverse("admin:article_collections_collection_changelist")
                    data = {
                        "action": "delete_selected",
                        "_selected_action": [collection.pk],
                    }
                    confirmation = self.client.post(url, data)
                else:
                    url = reverse(
                        "admin:article_collections_collection_delete",
                        args=[collection.pk],
                    )
                    data = {}
                    confirmation = self.client.get(url)
                self.assertContains(
                    confirmation, "Сами статьи и изображения останутся на сайте."
                )
                self.assertContains(confirmation, "Карточки статей в подборке")
                self.assertNotContains(confirmation, "Статьи подборки:")
                response = self.client.post(url, {**data, "post": "yes"})
                self.assertEqual(response.status_code, 302)
                self.assertFalse(Collection.objects.filter(pk=collection.pk).exists())
                self.assertFalse(CollectionItem.objects.filter(pk=item.pk).exists())
                self.article.refresh_from_db()
                self.assertEqual(self.article.content, original_content)
                self.assertEqual(
                    self.client.get(self.article.get_absolute_url()).status_code, 200
                )
                self.assertTrue(Image.objects.filter(pk=image.pk).exists())
                self.assertTrue(
                    CollectionItem.objects.filter(pk=other_item.pk).exists()
                )
                self.assertTrue(
                    Collection.objects.filter(pk=self.collection.pk).exists()
                )

    def test_picker_only_embedded_images_and_search(self):
        embedded = self.client.post(self.upload, {"upload": uploaded_image()}).json()
        illustration = Image.objects.create(
            title="Only illustration", file="images/link.png"
        )
        self.article.content = (
            f'<img src="{embedded["url"]}">'
            f'<a href="{illustration.file.url}" data-illustration="true">Illustration</a>'
        )
        self.article.save()
        self.assertEqual(
            list(article_images(self.article).values_list("pk", flat=True)),
            [embedded["id"]],
        )
        response = self.client.get(
            self.picker, {"scope": "article", "article": self.article.pk}
        )
        self.assertEqual(
            [image["id"] for image in response.json()["images"]], [embedded["id"]]
        )
        response = self.client.get(
            self.picker, {"scope": "all", "q": "Only illustration"}
        )
        self.assertEqual(
            [image["id"] for image in response.json()["images"]], [illustration.pk]
        )
        self.assertEqual(
            self.client.get(self.picker, {"scope": "article"}).json()["images"], []
        )

    def test_upload_and_prepare_follow_image_rules(self):
        result = self.client.post(self.upload, {"upload": uploaded_image((640, 480))})
        self.assertEqual(result.status_code, 201)
        image = Image.objects.get()
        self.assertEqual(image.renditions.count(), 2)
        self.assertEqual(result.json()["width"], 320)
        prepare = reverse("admin:collection_image_prepare", args=[image.pk])
        self.assertEqual(self.client.post(prepare).status_code, 200)
        self.assertEqual(image.renditions.count(), 2)
        self.assertEqual(self.client.get(prepare).status_code, 405)
        invalid = SimpleUploadedFile("bad.png", b"MZ executable")
        self.assertEqual(
            self.client.post(self.upload, {"upload": invalid}).status_code, 400
        )
        self.assertEqual(self.client.post(self.upload).status_code, 400)
        config = SiteSettings.objects.get()
        config.allow_image_png = False
        config.save()
        self.assertEqual(
            self.client.post(self.upload, {"upload": uploaded_image()}).status_code, 400
        )

    def test_editor_permissions_and_csrf(self):
        staff = get_user_model().objects.create_user(username="limited", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.picker).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="add_collection"))
        self.assertEqual(self.client.get(self.picker).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="view_image"))
        self.assertEqual(self.client.get(self.picker).status_code, 200)
        self.assertEqual(
            self.client.get(
                self.picker, {"scope": "article", "article": self.article.pk}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(self.upload, {"upload": uploaded_image()}).status_code, 403
        )
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(
            csrf.post(self.upload, {"upload": uploaded_image()}).status_code, 403
        )

    def test_admin_inline_order_and_image_widget(self):
        second = Article.objects.create(title="Second", content="")
        payload = {
            "title": "New collection",
            "slug": "new",
            "template_name": DEFAULT_TEMPLATE,
            "is_published": "on",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
        }
        for index, article in enumerate((self.article, second)):
            payload.update(
                {
                    f"items-{index}-article": article.pk,
                    f"items-{index}-title": "",
                    f"items-{index}-annotation": "Summary",
                    f"items-{index}-link_text": "Читать далее",
                    f"items-{index}-position": 1 - index,
                }
            )
        result = self.client.post(
            reverse("admin:article_collections_collection_add"), payload
        )
        self.assertEqual(result.status_code, 302)
        collection = Collection.objects.get(slug="new")
        self.assertEqual(
            list(collection.items.values_list("article_id", flat=True)),
            [second.pk, self.article.pk],
        )
        response = self.client.get(
            reverse("admin:article_collections_collection_change", args=[collection.pk])
        )
        self.assertContains(response, "Выбрать изображение")
        self.assertNotContains(response, 'id="add_id_items-0-image"')

    def test_preview_and_image_usage_and_internal_links(self):
        self.client.post(self.upload, {"upload": uploaded_image()})
        image = Image.objects.get()
        self.item(image=image)
        other = Article.objects.create(title="Other", content="")
        self.item(other, image=image)
        response = self.client.get("/history/")
        self.assertContains(response, 'class="collection-entry-image"', count=2)
        attach_image_pages([image])
        self.assertEqual(image.used_pages, [("/history/", "History")])
        self.article.content = '<a href="/history/">History</a>'
        self.assertEqual(
            linked_site_pages(self.article, "http://testserver/"),
            [("/history/", "History", "")],
        )
        image.file.delete(save=False)
        self.assertEqual(self.client.get("/history/").status_code, 200)
