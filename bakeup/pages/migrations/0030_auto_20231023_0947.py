# Generated by Django 3.2.12 on 2023-10-23 07:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0029_generalsettings_legal_entity'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailsettings',
            name='email_order_cancellation',
            field=models.TextField(blank=True, default='Sie haben soeben Ihre komplette Bestellung für den {{ production_day }} gelöscht. Wenn dies ein Versehen war, bestellen Sie die gelöschten Backwaren bitte wieder neu.', help_text='Bestellbestätigungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ price_total }}, {{ production_day }}, {{ order_count }}, {{ order_link }}, {{ point_of_sale }}', null=True),
        ),
        migrations.AddField(
            model_name='emailsettings',
            name='email_order_cancellation_subject',
            field=models.CharField(default='Ihre Bestellung für den {{ production_day }} wurde storniert', help_text='Betreff Storno E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}, {{ order_link }}', max_length=1024),
        ),
        migrations.AddField(
            model_name='emailsettings',
            name='send_email_order_cancellation',
            field=models.BooleanField(default=False, help_text='Soll eine Storno E-Mail versendet werden?', verbose_name='Storno E-Mail versenden?'),
        ),
    ]
