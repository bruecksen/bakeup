# Generated by Django 3.2.12 on 2022-10-31 09:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_generate_tokens'),
    ]

    operations = [
        migrations.AlterField(
            model_name='token',
            name='ttl',
            field=models.IntegerField(default=30, help_text='Days till token expires'),
        ),
    ]