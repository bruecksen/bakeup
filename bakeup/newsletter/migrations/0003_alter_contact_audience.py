# Generated by Django 4.2.11 on 2024-08-22 20:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("newsletter", "0002_newsletterlistpage_content"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contact",
            name="audience",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contacts",
                to="newsletter.audience",
            ),
        ),
    ]