from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from .links import linked_article_slugs
from .models import Article


class ArticleLinkWarningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="link_editor")
        cls.target = Article.objects.create(
            title="Draft <strong>title</strong>",
            slug="target",
            content="Text",
            is_published=False,
        )
        cls.source = Article.objects.create(
            title="Source",
            slug="source",
            content='<p><a href="/articles/target/">Read</a></p>',
        )

    def setUp(self):
        self.client.force_login(self.user)

    def save_article(self, article, **changes):
        data = {
            "title": article.title,
            "slug": article.slug,
            "content": article.content,
            "is_published": article.is_published,
        }
        data.update(changes)
        response = self.client.post(
            reverse("admin:articles_article_change", args=[article.pk]),
            data,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][1], 302)
        article.refresh_from_db()
        return [
            str(message)
            for message in get_messages(response.wsgi_request)
            if message.level == messages.WARNING
        ]

    def test_saving_published_article_warns_without_changing_links(self):
        content = self.source.content
        warnings = self.save_article(self.source)
        self.assertEqual(len(warnings), 1)
        self.assertIn("неопубликованные статьи", warnings[0])
        self.assertIn("&lt;strong&gt;title&lt;/strong&gt;", warnings[0])
        self.assertIn(
            reverse("admin:articles_article_change", args=[self.target.pk]), warnings[0]
        )
        self.assertEqual(self.source.content, content)
        self.assertTrue(self.source.is_published)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_published)

    def test_relative_absolute_and_repeated_links_are_deduplicated(self):
        content = (
            '<a href="../target/?a=1&amp;b=2#section">Relative</a>'
            '<a href="http://testserver/articles/%74arget">Absolute</a>'
            '<a href="//testserver/articles/target/">Same site</a>'
        )
        warnings = self.save_article(self.source, content=content)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].count("<a href="), 1)

    def test_no_warning_for_external_missing_or_published_targets(self):
        warnings = self.save_article(
            self.source,
            content=(
                '<a href="https://elsewhere.example/articles/target/">External</a>'
                '<a href="/articles/missing/">Missing</a>'
                '<a href="/articles/source/">Published</a>'
            ),
        )
        self.assertEqual(warnings, [])
        self.assertEqual(self.save_article(self.source, is_published=False), [])

    def test_unpublishing_warns_only_about_published_sources(self):
        self.target.is_published = True
        self.target.save()
        Article.objects.create(
            title="Hidden source", content=self.source.content, is_published=False
        )
        warnings = self.save_article(self.target, is_published=False)
        self.assertEqual(len(warnings), 1)
        self.assertIn("Статья снята", warnings[0])
        self.assertIn(">Source</a>", warnings[0])
        self.assertNotIn("Hidden source", warnings[0])
        self.assertFalse(self.target.is_published)
        self.assertEqual(
            self.client.get(self.target.get_absolute_url()).status_code, 404
        )
        self.assertEqual(self.save_article(self.target), [])

    def test_unpublishing_with_slug_change_finds_previous_links(self):
        self.target.is_published = True
        self.target.save()
        warnings = self.save_article(self.target, slug="new-target", is_published=False)
        self.assertEqual(len(warnings), 1)
        self.assertIn(">Source</a>", warnings[0])

    def test_link_parser_ignores_non_article_urls_and_malformed_hosts(self):
        self.assertEqual(
            linked_article_slugs(
                '<a href="http://[broken/">Bad</a>'
                '<a href="mailto:user@example.com">Mail</a>'
                '<a href="https://testserver.evil.example/articles/target/">External</a>'
                '<a href="/media/images/test.png">Image</a>'
                '<a href="#here">Self</a>',
                "http://testserver/articles/source/",
            ),
            {"source"},
        )


class ArticlePageLinksTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_superuser(username="page_link_editor")
        self.client.force_login(user)
        self.target = Article.objects.create(
            title="Материал <strong>без публикации</strong>",
            slug="linked-draft",
            content="Текст",
            is_published=False,
        )
        self.source = Article.objects.create(
            title="Ссылки",
            slug="page-links",
            content=(
                '<a href="/">Главная</a>'
                '<a href="../linked-draft/?a=1#part">Материал</a>'
                '<a href="http://testserver/articles/linked-draft/">Повтор</a>'
                '<a href="/articles/missing/">Отсутствующая статья</a>'
                '<a href="https://elsewhere.example/articles/external/">Внешняя</a>'
                '<a href="/media/images/image.png">Иллюстрация</a>'
                '<a href="/documents/1/download/">Документ</a>'
                '<a href="/admin/">Админка</a>'
            ),
        )
        self.url = reverse("admin:articles_article_change", args=[self.source.pk])

    def test_page_links_before_created_with_status_and_new_tab(self):
        response = self.client.get(self.url)
        html = response.content.decode()
        links = html.split('class="form-row field-page_links"', 1)[1].split(
            'class="form-row field-created_at"', 1
        )[0]
        self.assertIn("Ссылки на страницы", links)
        self.assertIn(
            'href="/" target="_blank" rel="noopener noreferrer">Главная страница</a>',
            links,
        )
        self.assertEqual(links.count('href="/articles/linked-draft/"'), 1)
        self.assertIn("Материал &lt;strong&gt;без публикации&lt;/strong&gt;", links)
        self.assertIn("не опубликовано", links)
        self.assertIn("страница не найдена", links)
        for ignored in (
            "elsewhere.example",
            "/media/",
            "/documents/",
            'href="/admin/"',
        ):
            self.assertNotIn(ignored, links)

    def test_page_links_follow_saved_content_title_and_publication(self):
        self.target.title = "Новое название"
        self.target.is_published = True
        self.target.save()
        response = self.client.get(self.url)
        self.assertContains(response, 'rel="noopener noreferrer">Новое название</a>')
        self.source.content = "<p>Без ссылок</p>"
        self.source.save()
        self.assertContains(self.client.get(self.url), "Ссылок на страницы сайта нет.")

    def test_add_form_handles_missing_article(self):
        self.assertContains(
            self.client.get(reverse("admin:articles_article_add")),
            "Ссылок на страницы сайта нет.",
        )
