# Generated by Django 3.2.12 on 2023-05-08 18:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0024_alter_productmapping_production_day'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_published',
            field=models.BooleanField(default=False),
        ),
    ]
