# Generated by Django 3.2.12 on 2022-07-31 10:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0001_initial'),
        ('shop', '0007_auto_20220719_1713'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pointofsale',
            name='address',
            field=models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='contrib.address'),
        ),
    ]