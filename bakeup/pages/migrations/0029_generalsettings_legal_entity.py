# Generated by Django 3.2.12 on 2023-09-03 19:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0028_auto_20230903_1023'),
    ]

    operations = [
        migrations.AddField(
            model_name='generalsettings',
            name='legal_entity',
            field=models.CharField(blank=True, max_length=1024, null=True),
        ),
    ]