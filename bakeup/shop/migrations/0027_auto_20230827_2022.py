# Generated by Django 3.2.12 on 2023-08-27 18:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0042_alter_instruction_instruction'),
        ('shop', '0026_auto_20230827_2016'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productiondayproduct',
            name='max_quantity',
            field=models.PositiveSmallIntegerField(verbose_name='Max quantity'),
        ),
        migrations.AlterField(
            model_name='productiondayproduct',
            name='product',
            field=models.ForeignKey(limit_choices_to={'is_sellable': True}, on_delete=django.db.models.deletion.PROTECT, related_name='production_days', to='workshop.product', verbose_name='Product'),
        ),
    ]