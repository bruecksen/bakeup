# Generated by Django 3.2.12 on 2022-04-28 13:41

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_auto_20220428_1541'),
        ('workshop', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='productionplan',
            name='production_day',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='production_plans', to='shop.productionday'),
        ),
        migrations.AlterField(
            model_name='productionplan',
            name='parent_plan',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='workshop.productionplan'),
        ),
    ]