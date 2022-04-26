# Generated by Django 3.2.12 on 2022-04-26 07:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0012_alter_productionplan_duration'),
        ('shop', '0018_remove_productiondayproduct_is_open_for_orders'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customerorder',
            name='production_plan',
        ),
        migrations.AddField(
            model_name='customerorderposition',
            name='production_plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='orders', to='workshop.productionplan'),
        ),
    ]
