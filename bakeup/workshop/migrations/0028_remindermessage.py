# Generated by Django 3.2.12 on 2023-05-31 12:55

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0019_alter_customerorder_options'),
        ('workshop', '0027_remove_product_is_published'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReminderMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_archived', models.BooleanField(default=False)),
                ('state', models.IntegerField(choices=[(0, 'Planned'), (1, 'Sent')], default=0)),
                ('subject', models.TextField()),
                ('body', models.TextField()),
                ('send_log', models.JSONField(default=dict)),
                ('error_log', models.JSONField(default=dict)),
                ('sent_date', models.DateTimeField(blank=True, null=True)),
                ('point_of_sale', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='shop.pointofsale')),
                ('production_day', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shop.productionday')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]