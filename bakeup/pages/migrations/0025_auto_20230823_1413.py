# Generated by Django 3.2.12 on 2023-08-23 12:13

import bakeup.pages.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0025_auto_20230828_1052'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailsettings',
            name='email_order_confirm',
            field=models.TextField(blank=True, help_text='Bestellbestätigungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}, {{ order_link }}', null=True),
        ),
        migrations.AlterField(
            model_name='emailsettings',
            name='email_order_confirm_subject',
            field=models.CharField(default='Vielen Dank für Deine Bestellung', help_text='Betreff Bestellbestätigungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}, {{ order_link }}', max_length=1024),
        ),
        migrations.AlterField(
            model_name='emailsettings',
            name='production_day_reminder_body',
            field=models.TextField(default=bakeup.pages.models.get_production_day_reminder_body, help_text='Erinnerungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}'),
        ),
        migrations.AlterField(
            model_name='emailsettings',
            name='production_day_reminder_subject',
            field=models.CharField(default='Deine Bestellung ist abholbereit', help_text='Betreff Erinnerungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}', max_length=1024),
        ),
    ]