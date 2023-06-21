# Generated by Django 3.2.12 on 2023-06-21 09:07

from django.db import migrations, models
import wagtail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0008_auto_20230608_1602'),
    ]

    operations = [
        migrations.CreateModel(
            name='CheckoutSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('show_terms', models.BooleanField(default=False, verbose_name='Checkbox AGB anzeigen?')),
                ('terms_text', wagtail.fields.RichTextField(blank=True, null=True, verbose_name='AGB Text')),
            ],
            options={
                'verbose_name': 'Brand settings',
            },
        ),
    ]
