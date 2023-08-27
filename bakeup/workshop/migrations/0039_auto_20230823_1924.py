# Generated by Django 3.2.12 on 2023-08-23 17:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0038_auto_20230823_1920'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='is_buyable',
            field=models.BooleanField(default=False, verbose_name='Is buyable'),
        ),
        migrations.AlterField(
            model_name='product',
            name='is_composable',
            field=models.BooleanField(default=False, verbose_name='Is composable'),
        ),
        migrations.AlterField(
            model_name='product',
            name='is_sellable',
            field=models.BooleanField(default=False, verbose_name='Is sellable'),
        ),
        migrations.AlterField(
            model_name='product',
            name='name',
            field=models.CharField(max_length=255, verbose_name='Name'),
        ),
    ]