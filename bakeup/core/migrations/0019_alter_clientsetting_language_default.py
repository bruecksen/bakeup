# Generated by Django 3.2.12 on 2023-08-28 08:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_auto_20230822_1013'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientsetting',
            name='language_default',
            field=models.CharField(choices=[('de', 'Deutsch'), ('de-DE@formal', 'Deutsch formal'), ('en', 'Englisch')], default='de-DE', max_length=12),
        ),
    ]
