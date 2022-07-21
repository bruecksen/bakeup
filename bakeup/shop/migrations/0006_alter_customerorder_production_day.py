# Generated by Django 3.2.12 on 2022-05-17 13:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_alter_productiondayproduct_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customerorder',
            name='production_day',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='customer_orders', to='shop.productionday'),
        ),
    ]
