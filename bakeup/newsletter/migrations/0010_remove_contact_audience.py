# Generated by Django 4.2.11 on 2024-09-02 08:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("newsletter", "0009_contact_audiences_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="contact",
            name="audience",
        ),
    ]
