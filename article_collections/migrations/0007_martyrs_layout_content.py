"""Rename the layout and separate imported captions and source attribution."""

import re

from django.db import migrations

OLD = "article_collections/layouts/martyrs.html"
NEW = "article_collections/layouts/novomucheniki-lotoshinskogo-okruga.html"
SOURCE_START = "Материал найден, собран и подготовлен"
DATES = re.compile(r"\d{1,4}(?:\.\d{1,4}){0,2}\s*[—–-]\s*\d{1,4}(?:\.\d{1,4}){0,2}")


def forwards(apps, schema_editor):
    Collection = apps.get_model("article_collections", "Collection")
    Item = apps.get_model("article_collections", "CollectionItem")
    db = schema_editor.connection.alias
    for collection in Collection.objects.using(db).filter(template_name=OLD):
        collection.template_name = NEW
        before, marker, after = collection.introduction.partition(SOURCE_START)
        if marker and not collection.closing_text:
            collection.introduction = before.rstrip()
            collection.closing_text = marker + after
        collection.save(
            using=db, update_fields=["template_name", "introduction", "closing_text"]
        )
        for item in Item.objects.using(db).filter(collection_id=collection.pk):
            caption, separator, annotation = item.annotation.partition("\n\n")
            if (
                not item.image_caption
                and separator
                and DATES.fullmatch(caption.strip())
            ):
                item.image_caption = caption.strip()
                item.annotation = annotation
                item.save(using=db, update_fields=["image_caption", "annotation"])


def backwards(apps, schema_editor):
    Collection = apps.get_model("article_collections", "Collection")
    Item = apps.get_model("article_collections", "CollectionItem")
    db = schema_editor.connection.alias
    for collection in Collection.objects.using(db).filter(template_name=NEW):
        collection.template_name = OLD
        if collection.closing_text:
            collection.introduction = "\n\n".join(
                filter(None, [collection.introduction, collection.closing_text])
            )
            collection.closing_text = ""
        collection.save(
            using=db, update_fields=["template_name", "introduction", "closing_text"]
        )
        for item in (
            Item.objects.using(db)
            .filter(collection_id=collection.pk)
            .exclude(image_caption="")
        ):
            item.annotation = "\n\n".join(
                filter(None, [item.image_caption, item.annotation])
            )
            item.image_caption = ""
            item.save(using=db, update_fields=["image_caption", "annotation"])


class Migration(migrations.Migration):
    dependencies = [
        (
            "article_collections",
            "0006_collection_closing_text_collectionitem_image_caption",
        )
    ]
    operations = [migrations.RunPython(forwards, backwards)]
