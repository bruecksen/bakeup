# Generated by Django 4.2.11 on 2024-08-26 07:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_clientsetting_is_newsletter_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientsetting",
            name="email_name",
            field=models.CharField(blank=True, max_length=1024, null=True),
        ),
    ]
