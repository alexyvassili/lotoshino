from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import ArticleForm
from .html import clean_article_html
from .models import Article


class ArticleEditorTests(TestCase):
    def test_annotation_survives_save_and_render_without_arbitrary_classes(self):
        form = ArticleForm(
            data={
                "title": "Annotation",
                "is_published": True,
                "content": '<p class="article-annotation unwanted" onclick="bad()" style="color:red">'
                'Текст <strong>аннотации</strong></p><p class="article-annotation">Продолжение</p>'
                '<p class="unwanted">Обычный абзац</p>',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        article = form.save()
        article.refresh_from_db()
        self.assertEqual(article.content.count('class="article-annotation"'), 2)
        for forbidden in ("unwanted", "onclick", "color:red"):
            self.assertNotIn(forbidden, article.content)
        self.assertEqual(clean_article_html(article.content), article.content)
        self.assertContains(
            self.client.get(article.get_absolute_url()), article.content
        )

    def test_actual_dimension_names_survive_html_cleanup(self):
        for name in (
            "a" * 32 + ".jpg",
            "a" * 32 + "_320x222.jpg",
            "a" * 32 + "_320x222_Ab12xYz.png",
            "01234567-89ab-4def-8123-456789abcdef.png",
            "01234567-89ab-4def-8123-456789abcdef_320x222.jpg",
        ):
            url = "/media/images/" + name
            content = f'<img src="{url}" data-full-size="{url}">'
            self.assertEqual(clean_article_html(content), content)

    def test_local_illustrations_survive_save_even_when_file_is_missing(self):
        for url in (
            "/media/images/missing.png",
            "/not-an-image/",
            "/media/documents/test.pdf",
        ):
            with self.subTest(url=url):
                form = ArticleForm(
                    data={
                        "title": "Иллюстрация",
                        "is_published": True,
                        "content": f'<p><a href="{url}" data-illustration="true">Смотреть</a></p>',
                    }
                )
                self.assertTrue(form.is_valid(), form.errors)
                article = form.save()
                article.refresh_from_db()
                self.assertIn('data-illustration="true"', article.content)
                self.assertContains(
                    self.client.get(article.get_absolute_url()),
                    'data-illustration="true"',
                )

    def test_external_illustrations_are_rejected_and_model_save_removes_flag(self):
        for url in (
            "https://example.com/image.png",
            "//example.com/image.png",
            "/\\example.com/image.png",
            "/%2fexample.com/image.png",
            "javascript:alert(1)",
            "images/test.png",
            "",
        ):
            with self.subTest(url=url):
                content = f'<a href="{url}" data-illustration="true">Иллюстрация</a>'
                form = ArticleForm(data={"title": "External", "content": content})
                self.assertFalse(form.is_valid())
                self.assertIn("Ссылки на внешние сайты", str(form.errors))
                article = Article.objects.create(title="External", content=content)
                self.assertNotIn("data-illustration", article.content)
        form = ArticleForm(
            data={
                "title": "Ordinary link",
                "content": '<a href="https://example.com/">Сайт</a>',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_illustration_sanitization_handles_quoted_markup_and_newlines(self):
        content = '<p>Текст</p>\n<a title="&gt;" href="https://example.com/" data-illustration="true">Внешняя</a>\n<a href="/image.png" data-illustration="true">Местная</a>'
        cleaned = clean_article_html(content)
        self.assertEqual(cleaned.count('data-illustration="true"'), 1)
        self.assertIn('href="/image.png" data-illustration="true"', cleaned)

    def test_viewer_setting_belongs_to_each_insertion_and_survives_save(self):
        preview = "/media/images/" + "a" * 32 + ".jpg"
        full = "/media/images/" + "b" * 32 + ".jpg"
        for enabled in ("true", "false"):
            with self.subTest(enabled=enabled):
                form = ArticleForm(
                    data={
                        "title": f"Viewer {enabled}",
                        "is_published": True,
                        "content": f'<figure class="image"><img data-viewer="{enabled}" data-full-size="{full}" src="{preview}"></figure>',
                    }
                )
                self.assertTrue(form.is_valid(), form.errors)
                article = form.save()
                article.refresh_from_db()
                self.assertIn(f'data-viewer="{enabled}"', article.content)
                self.assertIn(f'data-full-size="{full}"', article.content)
                response = self.client.get(article.get_absolute_url())
                self.assertContains(response, article.content)
                self.assertContains(
                    response, 'type="module" src="/static/articles/image_viewer.js?v=4"'
                )
                self.assertContains(response, 'data-image-base="/media/images/"')

    def test_viewer_metadata_only_allows_known_values_and_library_urls(self):
        for url in (
            "javascript:alert(1)",
            "https://example.com/photo.jpg",
            "/media/documents/test.pdf",
        ):
            with self.subTest(url=url):
                cleaned = clean_article_html(
                    f'<img src="/media/images/{"a" * 32}.jpg" data-viewer="anything" data-full-size="{url}" onclick="alert(1)">'
                )
                self.assertNotIn("data-viewer", cleaned)
                self.assertNotIn("data-full-size", cleaned)
                self.assertNotIn("onclick", cleaned)

    def test_preview_and_full_image_link_survive_save_and_display(self):
        preview = "/media/images/" + "a" * 32 + ".jpg"
        full = "/media/images/" + "b" * 32 + ".jpg"
        form = ArticleForm(
            data={
                "title": "Размеры",
                "is_published": True,
                "content": f'<figure class="image"><a href="{full}"><img src="{preview}" width="320" height="240" alt="Храм"></a></figure>',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        article = form.save()
        self.assertIn(f'href="{full}"', article.content)
        self.assertIn(f'src="{preview}"', article.content)
        response = self.client.get(article.get_absolute_url())
        self.assertContains(response, f'href="{full}"')
        self.assertContains(response, f'src="{preview}"')

    def test_image_styles_survive_save_and_edit(self):
        for index, image_style in enumerate(
            ("", " image-style-align-left", " image-style-align-right")
        ):
            with self.subTest(image_style=image_style):
                content = (
                    f'<figure class="image image_resized{image_style}" style="width:50%;">'
                    '<img src="/media/images/0123456789abcdef0123456789abcdef.png" '
                    'alt="Храм" width="800" height="600"><figcaption>Подпись</figcaption>'
                    "</figure><p>Текст статьи.</p>"
                )
                form = ArticleForm(
                    data={
                        "title": "Статья",
                        "slug": f"article-{index}",
                        "content": content,
                    }
                )
                self.assertTrue(form.is_valid(), form.errors)
                article = form.save()
                article.refresh_from_db()
                self.assertIn('style="width:50%;"', article.content)
                self.assertIn(
                    f'class="image image_resized{image_style}"', article.content
                )
                self.assertIn("Подпись", article.content)
                self.assertEqual(clean_article_html(article.content), article.content)

    def test_dangerous_html_is_removed_on_model_save(self):
        article = Article.objects.create(
            title="Проверка",
            slug="check",
            content='<script>alert(1)</script><p onclick="alert(1)">Текст</p>'
            '<a href="javascript:alert(1)">Ссылка</a>'
            '<img src="https://external.example/image.svg" onerror="alert(1)">'
            '<figure style="width:50%;position:fixed" class="image evil"></figure>',
        )
        for forbidden in (
            "script",
            "onclick",
            "onerror",
            "javascript:",
            "external.example",
            "position",
            "evil",
        ):
            self.assertNotIn(forbidden, article.content)
        self.assertIn("Текст", article.content)

    def test_empty_formatted_text_is_rejected(self):
        form = ArticleForm(data={"title": "Статья", "content": "<p>&nbsp;</p>"})
        self.assertFalse(form.is_valid())
        self.assertIn("content", form.errors)


class ArticlePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.article = Article.objects.create(
            title="История храма",
            slug="istoriya-hrama",
            content='<figure class="image image-style-align-left">'
            '<img src="/media/images/0123456789abcdef0123456789abcdef.png" alt="Храм">'
            "</figure><p>История <strong>храма</strong>.</p>",
        )

    def test_public_page_preserves_formatting_and_image_styles(self):
        self.assertEqual(self.article.get_absolute_url(), "/articles/istoriya-hrama/")
        response = self.client.get(self.article.get_absolute_url())
        self.assertContains(
            response, '<h1 class="mainblock-header">История храма</h1>', html=True
        )
        self.assertContains(response, self.article.content)
        self.assertContains(response, "articles/content.css")
        self.assertEqual(
            self.client.head(self.article.get_absolute_url()).status_code, 200
        )
        self.assertEqual(
            self.client.post(self.article.get_absolute_url()).status_code, 405
        )

    def test_unknown_slug_returns_404(self):
        self.assertEqual(self.client.get("/articles/missing/").status_code, 404)

    def test_stable_url_on_title_change(self):
        url = self.article.get_absolute_url()
        self.article.title = "Другой заголовок"
        self.article.save()
        self.assertEqual(self.article.get_absolute_url(), url)
        self.assertContains(self.client.get(url), "Другой заголовок")

    def test_duplicate_slug_is_rejected_in_form(self):
        form = ArticleForm(
            data={
                "title": "Другая статья",
                "slug": self.article.slug,
                "content": "Текст",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("slug", form.errors)

    def test_public_page_sanitizes_html_even_if_save_was_bypassed(self):
        Article.objects.filter(pk=self.article.pk).update(
            content='<p onclick="alert(1)">Текст</p><script>alert(1)</script>'
        )
        response = self.client.get(self.article.get_absolute_url())
        self.assertContains(response, "<p>Текст</p>", html=True)
        self.assertNotContains(response, "alert(1)")

    def test_admin_has_view_on_site_link(self):
        user = get_user_model().objects.create_superuser(
            username="editor", password="test"
        )
        self.client.force_login(user)
        response = self.client.get(
            reverse("admin:articles_article_change", args=[self.article.pk])
        )
        self.assertContains(response, 'class="viewsitelink"')
        self.assertContains(response, 'name="slug"')


class ArticleSlugTests(TestCase):
    def test_empty_form_slug_is_generated_in_latin(self):
        form = ArticleForm(
            data={
                "title": "История храма",
                "content": "<p>Текст</p>",
                "is_published": True,
            }
        )
        self.assertFalse(form.fields["slug"].required)
        self.assertIn("Если адрес не заполнен", form.fields["slug"].help_text)
        self.assertTrue(form.is_valid(), form.errors)
        article = form.save()
        self.assertEqual(article.slug, "istoriya-hrama")
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 200)

    def test_model_save_generates_unique_slugs_within_max_length(self):
        for title in ("История храма", "Щ" * 255, "!!!"):
            with self.subTest(title=title):
                first = Article.objects.create(title=title, content="Текст")
                second = Article.objects.create(title=title, content="Текст")
                self.assertNotEqual(first.slug, second.slug)
                self.assertTrue(second.slug.endswith("-2"))
                self.assertLessEqual(len(second.slug), 255)
                self.assertRegex(second.slug, r"^[a-z0-9_-]+$")

    def test_custom_slug_is_preserved_and_cyrillic_input_is_rejected(self):
        form = ArticleForm(
            data={
                "title": "История храма",
                "slug": "custom-address",
                "content": "Текст",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().slug, "custom-address")
        invalid = ArticleForm(
            data={"title": "История храма", "slug": "история-храма", "content": "Текст"}
        )
        self.assertFalse(invalid.is_valid())
        self.assertIn("slug", invalid.errors)

    def test_clearing_slug_regenerates_it_on_partial_save(self):
        article = Article.objects.create(title="История храма", content="Текст")
        article.title = "Новый заголовок"
        article.slug = ""
        article.save(update_fields=["title", "slug"])
        article.refresh_from_db()
        self.assertEqual(article.slug, "novyy-zagolovok")


class ArticlePublicationTests(TestCase):
    def test_new_articles_are_published_by_default(self):
        self.assertTrue(ArticleForm()["is_published"].value())
        article = Article.objects.create(title="Published", content="Text")
        self.assertTrue(article.is_published)
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 200)

    def test_unchecked_checkbox_saves_unpublished_article(self):
        form = ArticleForm(data={"title": "Draft", "content": "Draft text"})
        self.assertTrue(form.is_valid(), form.errors)
        article = form.save()
        self.assertFalse(article.is_published)
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.head(article.get_absolute_url()).status_code, 404)

    def test_admin_can_unpublish_and_republish_existing_article(self):
        user = get_user_model().objects.create_superuser(username="publisher")
        self.client.force_login(user)
        article = Article.objects.create(title="Article", content="Text")
        change_url = reverse("admin:articles_article_change", args=[article.pk])
        data = {
            "title": article.title,
            "slug": article.slug,
            "content": article.content,
        }
        self.assertEqual(self.client.post(change_url, data).status_code, 302)
        article.refresh_from_db()
        self.assertFalse(article.is_published)
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(change_url).status_code, 200)
        data["is_published"] = "on"
        self.assertEqual(self.client.post(change_url, data).status_code, 302)
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 200)

    def test_admin_add_form_checks_publication_by_default(self):
        user = get_user_model().objects.create_superuser(username="publisher")
        self.client.force_login(user)
        response = self.client.get(reverse("admin:articles_article_add"))
        self.assertTrue(response.context["adminform"].form["is_published"].value())
