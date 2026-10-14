from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from articles.links import linked_site_pages
from articles.models import Article
from media_library.models import Image
from media_library.tests import uploaded_image
from media_library.usage import attach_image_pages
from site_settings.models import SiteSettings

from .forms import CollectionForm, CollectionItemForm
from .images import article_images
from .layouts import DEFAULT_TEMPLATE, TEXT_TEMPLATE, collection_template_choices
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

    def test_text_collection_has_one_editor_and_saves_without_card_formset(self):
        content = '<figure class="table"><table style="border-style:none;"><tbody><tr><td style="border-style:none;"><p><a href="/articles/example/">Материал</a></p></td></tr></tbody></table></figure>'
        collection = Collection.objects.create(
            title="Азбука Православия",
            template_name=TEXT_TEMPLATE,
            introduction=content,
        )
        change_url = reverse(
            "admin:article_collections_collection_change", args=[collection.pk]
        )
        response = self.client.get(change_url)
        self.assertContains(response, "Содержимое:")
        self.assertNotContains(response, 'name="closing_text"')
        self.assertNotContains(response, 'id="items-group"')
        self.assertNotContains(response, 'name="template_name"')
        response = self.client.post(
            change_url,
            {
                "title": collection.title,
                "slug": collection.slug,
                "introduction": content.replace("Материал", "Новый текст"),
                "is_published": "on",
                "_save": "Сохранить",
            },
        )
        self.assertEqual(response.status_code, 302)
        collection.refresh_from_db()
        self.assertIn("Новый текст", collection.introduction)
        self.assertEqual(collection.items.count(), 0)
        response = Client().get(collection.get_absolute_url())
        self.assertTemplateUsed(response, TEXT_TEMPLATE)
        self.assertContains(response, 'style="border-style:none;"')
        self.assertContains(response, "Новый текст")
        self.assertNotContains(response, "Статьи скоро появятся")
        collection.is_published = False
        collection.save()
        self.assertEqual(Client().get(collection.get_absolute_url()).status_code, 404)

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
        self.assertNotContains(response, "<script>bad()</script>")
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

    def test_martyrs_captions_footer_and_admin_fields(self):
        collection = Collection.objects.create(
            title="Новомученики",
            slug="martyrs",
            template_name="article_collections/layouts/novomucheniki-lotoshinskogo-okruga.html",
            closing_text='<p>Источник <script>bad()</script></p><p><a href="mailto:editor@example.com">editor@example.com</a></p>',
        )
        CollectionItem.objects.create(
            collection=collection,
            article=self.article,
            annotation="Биография",
            image_caption="1881 — 1937",
        )
        response = Client().get(collection.get_absolute_url())
        self.assertContains(
            response,
            '<figcaption class="martyr-dates">1881 — 1937</figcaption>',
            html=True,
        )
        self.assertNotContains(response, "<script>bad()</script>")
        self.assertContains(response, 'href="mailto:editor@example.com"')
        html = response.content.decode()
        self.assertLess(html.index("Биография"), html.index('class="martyrs-source '))
        admin_response = self.client.get(
            reverse("admin:article_collections_collection_change", args=[collection.pk])
        )
        self.assertContains(admin_response, 'name="closing_text"')
        self.assertContains(admin_response, 'name="items-0-image_caption"')

    def test_martyrs_content_migration_preserves_text_and_other_collections(self):
        migration = import_module(
            "article_collections.migrations.0007_martyrs_layout_content"
        )
        original_intro = (
            "Вступление\n\nМатериал найден, собран и подготовлен редакцией."
        )
        original_annotation = "1881 — 27.11.1937\n\nБиография\n\nЕщё абзац."
        card = self.item(image_caption="")
        card.annotation = original_annotation
        card.save()
        Collection.objects.filter(pk=self.collection.pk).update(
            template_name=migration.OLD,
            introduction=original_intro,
        )
        other = Collection.objects.create(title="Other", introduction=original_intro)
        editor = SimpleNamespace(connection=connection)
        historical_apps = (
            MigrationLoader(connection)
            .project_state(
                [
                    (
                        "article_collections",
                        "0006_collection_closing_text_collectionitem_image_caption",
                    )
                ]
            )
            .apps
        )
        migration.forwards(historical_apps, editor)
        self.collection.refresh_from_db()
        card.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(self.collection.template_name, migration.NEW)
        self.assertEqual(
            self.collection.introduction + "\n\n" + self.collection.closing_text,
            original_intro,
        )
        self.assertEqual(
            card.image_caption + "\n\n" + card.annotation, original_annotation
        )
        self.assertEqual(other.introduction, original_intro)
        self.assertEqual(other.closing_text, "")
        migration.backwards(historical_apps, editor)
        self.collection.refresh_from_db()
        card.refresh_from_db()
        self.assertEqual(self.collection.introduction, original_intro)
        self.assertEqual(card.annotation, original_annotation)

    def test_collection_rich_text_forms_and_public_layouts(self):
        content = '<p class="article-annotation"><strong>Note</strong></p><p><a href="/">Home</a></p>'
        for index, (template, _) in enumerate(collection_template_choices()):
            form = CollectionForm(
                data={
                    "title": "Rich text",
                    "slug": f"rich-{index}",
                    "template_name": template,
                    "is_published": True,
                    "introduction": content,
                    "closing_text": content
                    + '<script>bad()</script><p onclick="bad()">End</p>',
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
            collection = form.save()
            self.assertNotIn("<script>", collection.closing_text)
            self.assertNotIn("onclick", collection.closing_text)
            response = Client().get(collection.get_absolute_url())
            editor_count = 1 if template == TEXT_TEMPLATE else 2
            self.assertContains(
                response,
                '<p class="article-annotation"><strong>Note</strong></p>',
                count=editor_count,
                html=True,
            )
            self.assertContains(
                response, 'data-image-base="/media/images/"', count=editor_count
            )
            self.assertNotContains(response, "&lt;p")
            admin_response = self.client.get(
                reverse(
                    "admin:article_collections_collection_change", args=[collection.pk]
                )
            )
            self.assertContains(
                admin_response, 'data-article-editor="true"', count=editor_count
            )
            self.assertContains(
                admin_response, reverse("admin:collection_image_upload")
            )
        for field in ("introduction", "closing_text"):
            form = CollectionForm(
                data={
                    "title": "Bad",
                    "template_name": DEFAULT_TEMPLATE,
                    field: '<p><a href="https://example.com/x.jpg" data-illustration="true">X</a></p>',
                }
            )
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_plain_collection_text_migration_escapes_and_keeps_paragraphs(self):
        migration = import_module(
            "article_collections.migrations.0008_collection_rich_text"
        )
        Collection.objects.filter(pk=self.collection.pk).update(
            introduction="First\n\nSecond <script>alert(1)</script>",
            closing_text="Contact editor@example.com",
        )
        registry = (
            MigrationLoader(connection)
            .project_state([("article_collections", "0007_martyrs_layout_content")])
            .apps
        )
        migration.forwards(registry, SimpleNamespace(connection=connection))
        self.collection.refresh_from_db()
        self.assertIn("<p>First</p>", self.collection.introduction)
        self.assertIn("&lt;script&gt;", self.collection.introduction)
        self.assertIn('href="mailto:editor@example.com"', self.collection.closing_text)

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
