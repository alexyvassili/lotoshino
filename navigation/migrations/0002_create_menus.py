from django.db import migrations


def create_menus(apps, schema_editor):
    Menu = apps.get_model("navigation", "Menu")
    alias = schema_editor.connection.alias
    for code in ("main", "top"):
        Menu.objects.using(alias).get_or_create(code=code)


class Migration(migrations.Migration):
    dependencies = [("navigation", "0001_initial")]
    operations = [migrations.RunPython(create_menus, migrations.RunPython.noop)]
