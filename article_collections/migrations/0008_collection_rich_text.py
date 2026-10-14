"""Existing fields contain plain text: escape it before enabling HTML editing."""
from django.db import migrations
from django.utils.html import escape, linebreaks, urlize


def forwards(apps, schema_editor):
    Collection = apps.get_model("article_collections", "Collection")
    for collection in Collection.objects.using(schema_editor.connection.alias).all():
        for field in ("introduction", "closing_text"):
            value = getattr(collection, field)
            if value:
                # Escape first: old text may contain literal HTML examples.
                setattr(collection, field, linebreaks(urlize(escape(value))))
        collection.save(using=schema_editor.connection.alias, update_fields=["introduction", "closing_text"])


class Migration(migrations.Migration):
    dependencies = [("article_collections", "0007_martyrs_layout_content")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
