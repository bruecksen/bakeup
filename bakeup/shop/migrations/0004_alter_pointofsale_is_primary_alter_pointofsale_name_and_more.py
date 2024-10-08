# Generated by Django 4.2.11 on 2024-06-27 23:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0003_alter_customerorderposition_product_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pointofsale",
            name="is_primary",
            field=models.BooleanField(default=False, verbose_name="Primary?"),
        ),
        migrations.AlterField(
            model_name="pointofsale",
            name="name",
            field=models.CharField(max_length=255, verbose_name="Name"),
        ),
        migrations.AlterField(
            model_name="pointofsale",
            name="short_name",
            field=models.CharField(
                blank=True, max_length=255, null=True, verbose_name="Short Name"
            ),
        ),
    ]
