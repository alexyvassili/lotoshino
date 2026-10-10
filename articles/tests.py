from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import ArticleForm
from .html import clean_article_html
from .models import Article


class ArticleEditorTests(TestCase):
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
        form = ArticleForm(data={"title": "История храма", "content": "<p>Текст</p>"})
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
