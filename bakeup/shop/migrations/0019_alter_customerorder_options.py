# Generated by Django 3.2.12 on 2023-04-20 09:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0018_auto_20230418_1109'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='customerorder',
            options={'ordering': ['production_day', '-created']},
        ),
    ]
