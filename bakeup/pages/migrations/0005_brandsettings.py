# Generated by Django 3.2.12 on 2023-05-16 14:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('wagtailimages', '0025_alter_image_file_alter_rendition_file'),
        ('pages', '0004_footersettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='BrandSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('primary_color', models.CharField(blank=True, help_text='as a hex value', max_length=8, null=True, verbose_name='Primary color')),
                ('secondary_color', models.CharField(blank=True, help_text='as a hex value', max_length=8, null=True, verbose_name='Primary color')),
                ('light_color', models.CharField(blank=True, help_text='as a hex value', max_length=8, null=True, verbose_name='Primary color')),
                ('dark_color', models.CharField(blank=True, help_text='as a hex value', max_length=8, null=True, verbose_name='Primary color')),
                ('logo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='wagtailimages.image', verbose_name='Image')),
            ],
            options={
                'verbose_name': 'Brand settings',
            },
        ),
    ]