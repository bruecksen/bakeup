# Generated by Django 3.2.12 on 2022-11-24 11:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0011_productionday_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='pointofsale',
            name='is_primary',
            field=models.BooleanField(default=False),
        ),
    ]
