# Generated by Django 3.2.12 on 2022-03-30 14:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0011_auto_20220330_1531'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productiondayproduct',
            name='production_day',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='production_day_products', to='shop.productionday'),
        ),
    ]
