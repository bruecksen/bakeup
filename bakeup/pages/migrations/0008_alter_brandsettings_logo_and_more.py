# Generated by Django 4.2.11 on 2024-08-07 12:42

from django.db import migrations, models
import django.db.models.deletion
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ("wagtailimages", "0026_delete_uploadedimage"),
        ("pages", "0007_alter_contentpage_content_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="brandsettings",
            name="logo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="wagtailimages.image",
                verbose_name="Logo",
            ),
        ),
        migrations.AlterField(
            model_name="emailsettings",
            name="email_footer",
            field=wagtail.fields.RichTextField(
                blank=True,
                help_text="Dieser Footer wird an jede Email angehängt.",
                null=True,
            ),
        ),
    ]