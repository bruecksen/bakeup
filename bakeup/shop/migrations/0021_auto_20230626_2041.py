# Generated by Django 3.2.12 on 2023-06-26 18:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contrib', '0001_initial'),
        ('shop', '0020_pointofsale_short_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='point_of_sale',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='customers', to='shop.pointofsale'),
        ),
        migrations.AlterField(
            model_name='pointofsale',
            name='address',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='contrib.address'),
        ),
    ]
