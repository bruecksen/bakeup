# Generated by Django 3.2.12 on 2023-05-31 08:54

from django.db import migrations, models
import wagtail.blocks
import wagtail.documents.blocks
import wagtail.fields
import wagtail.images.blocks


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0006_auto_20230530_1527'),
    ]

    operations = [
        migrations.AlterField(
            model_name='brandsettings',
            name='is_brand_theme_activated',
            field=models.BooleanField(default=False, verbose_name='Theme activated?'),
        ),
        migrations.AlterField(
            model_name='shoppage',
            name='banner_cta',
            field=wagtail.fields.StreamField([('buttons', wagtail.blocks.StructBlock([('text', wagtail.blocks.CharBlock(label='Text')), ('link', wagtail.blocks.StructBlock([('target', wagtail.blocks.StreamBlock([('page', wagtail.blocks.PageChooserBlock(icon='doc-empty-inverse', label='Page')), ('document', wagtail.documents.blocks.DocumentChooserBlock(icon='doc-full', label='Document')), ('image', wagtail.blocks.StructBlock([('alignment', wagtail.blocks.ChoiceBlock(choices=[('start', 'Left'), ('center', 'Centre'), ('end', 'Right')])), ('image', wagtail.images.blocks.ImageChooserBlock())], label='Image')), ('url', wagtail.blocks.URLBlock(label='External link')), ('anchor', wagtail.blocks.CharBlock(help_text='An anchor in the current page, for example: <code>#target-id</code>.', label='Anchor link'))], required=True))], required=True))]))], blank=True, null=True, use_json_field=None, verbose_name='Call to action'),
        ),
    ]
