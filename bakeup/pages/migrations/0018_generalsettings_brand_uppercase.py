# Generated by Django 3.2.12 on 2023-08-22 07:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0017_generalsettings_brand_font'),
    ]

    operations = [
        migrations.AddField(
            model_name='generalsettings',
            name='brand_uppercase',
            field=models.BooleanField(default=False, help_text='Brand name in Großbuchstaben'),
        ),
    ]