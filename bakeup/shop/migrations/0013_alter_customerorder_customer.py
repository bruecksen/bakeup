# Generated by Django 3.2.12 on 2022-03-30 20:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0012_alter_productiondayproduct_production_day'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customerorder',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='shop.customer'),
        ),
    ]
