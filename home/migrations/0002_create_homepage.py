from django.db import migrations


def create_homepage(apps, schema_editor):
    HomePage = apps.get_model("home", "HomePage")
    HomePage.objects.using(schema_editor.connection.alias).get_or_create(
        pk=1, defaults={"content": ""}
    )


class Migration(migrations.Migration):
    dependencies = [("home", "0001_initial")]

    operations = [migrations.RunPython(create_homepage, migrations.RunPython.noop)]
