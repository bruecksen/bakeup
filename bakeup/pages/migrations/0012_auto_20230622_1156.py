# Generated by Django 3.2.12 on 2023-06-22 09:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0011_auto_20230621_1118'),
    ]

    operations = [
        migrations.AlterField(
            model_name='checkoutsettings',
            name='order_button_change',
            field=models.CharField(default='Jetzt kostenpflichtig ändern', max_length=1024, verbose_name='Button Bestellung ändern'),
        ),
        migrations.AlterField(
            model_name='checkoutsettings',
            name='order_button_place',
            field=models.CharField(default='Jetzt kostenpflichtig bestellen', max_length=1024, verbose_name='Button bestellen'),
        ),
    ]