# Generated by Django 3.2.12 on 2022-03-29 09:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workshop', '0003_alter_instruction_product'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='category',
            name='category_id_and_parent_not_equal',
        ),
        migrations.RemoveField(
            model_name='category',
            name='parent',
        ),
        migrations.AddField(
            model_name='category',
            name='depth',
            field=models.PositiveIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='category',
            name='numchild',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='category',
            name='path',
            field=models.CharField(default=1, max_length=255, unique=True),
            preserve_default=False,
        ),
    ]