# Generated by Django 3.2.12 on 2022-03-28 08:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_pointofsale_address'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pointofsaleopeninghour',
            name='day_of_the_week',
            field=models.IntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')]),
        ),
    ]
