# Generated by Django 3.2.12 on 2022-05-12 13:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0002_auto_20220428_1541'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='image',
            field=models.FileField(blank=True, null=True, upload_to='product_images'),
        ),
    ]