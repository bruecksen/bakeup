# Generated by Django 4.2.11 on 2024-10-24 14:24

from django.db import migrations, models
import django.db.models.deletion
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailimages", "0026_delete_uploadedimage"),
        ("pages", "0013_alter_emailsettings_email_order_cancellation_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="generalsettings",
            name="bio_certification_logo",
            field=models.ForeignKey(
                blank=True,
                help_text="Logo wird in der Produktkachel angezeigt, wenn es ein Bio Produkt ist.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtailimages.image",
                verbose_name="Bio logo",
            ),
        ),
        migrations.AlterField(
            model_name="emailsettings",
            name="email_order_cancellation",
            field=wagtail.fields.RichTextField(
                blank=True,
                default="Sie haben soeben Ihre komplette Bestellung für den {{ production_day }} gelöscht. Wenn dies ein Versehen war, bestellen Sie die gelöschten Backwaren bitte wieder neu.",
                help_text="Bestellbestätigungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ price_total }}, {{ production_day }}, {{ order_count }}, {{ order_link }}, {{ order_link_text }}, {{ point_of_sale }}",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="emailsettings",
            name="email_order_confirm",
            field=wagtail.fields.RichTextField(
                blank=True,
                default="Vielen Dank für Ihre Bestellung, {{ first_name }} {{ last_name }}!\n\nHier eine Übersicht über Ihre Bestellung für den {{ production_day }}:\n\n{{ order }}\n\nGesamtpreis: {{ price_total }}\n\nIhre ausgewählte Abholstelle: {{ point_of_sale }}\n\nSie können Ihre Bestellung vor dem Backtag jederzeit in Ihrem Account unter {{ order_link\xa0}} anpassen oder stornieren.",
                help_text="Bestellbestätigungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ price_total }}, {{ production_day }}, {{ order_count }}, {{ order_link }}, {{ order_link_text }}, {{ point_of_sale }}",
                null=True,
            ),
        ),
    ]
