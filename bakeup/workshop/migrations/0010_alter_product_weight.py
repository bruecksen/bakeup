# Generated by Django 3.2.12 on 2022-07-19 08:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0009_auto_20220629_1113'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='weight',
            field=models.FloatField(default=1000, help_text='weight in grams'),
        ),
    ]
