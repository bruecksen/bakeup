# Generated by Django 4.2.11 on 2024-08-22 08:00

import bakeup.core.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("newsletter", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="newsletterlistpage",
            name="content",
            field=bakeup.core.fields.StreamField(blank=True, null=True),
        ),
    ]
