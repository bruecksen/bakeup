from django.db import migrations


def set_missing_uom(apps, schema_editor):
    UOM = apps.get_model("core", "UOM")
    Product = apps.get_model("workshop", "Product")
    g = UOM.objects.filter(abbreviation="g", base_unit__isnull=True).first()
    if g:
        Product.objects.filter(uom__isnull=True).update(uom=g)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_create_uom_entries"),
        ("workshop", "0011_copy_instructions_to_production_plans"),
    ]

    operations = [
        migrations.RunPython(set_missing_uom, migrations.RunPython.noop),
    ]
