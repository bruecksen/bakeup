# Generated by Django 3.2.12 on 2023-09-14 12:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('shop', '0031_productiondayproduct_group'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productiondayproduct',
            name='group',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.group', verbose_name='Group'),
        ),
    ]
