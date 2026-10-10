from django.db import migrations, models
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Article = apps.get_model("articles", "Article")
    articles = Article.objects.using(schema_editor.connection.alias)
    for article in articles.order_by("pk").iterator():
        base = slugify(article.title, allow_unicode=True)[:230] or "article"
        slug = base
        suffix = 1
        while articles.filter(slug=slug).exists():
            slug = f"{base}-{suffix}"
            suffix += 1
        articles.filter(pk=article.pk).update(slug=slug)


class Migration(migrations.Migration):
    dependencies = [("articles", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="article",
            name="slug",
            field=models.SlugField(max_length=255, allow_unicode=True, null=True),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="article",
            name="slug",
            field=models.SlugField(
                "Адрес статьи",
                max_length=255,
                unique=True,
                allow_unicode=True,
                help_text="Часть URL после /articles/. Буквы, цифры, дефисы и подчёркивания.",
            ),
        ),
    ]
