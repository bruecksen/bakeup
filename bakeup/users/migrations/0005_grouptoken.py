# Generated by Django 3.2.12 on 2023-09-20 08:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('users', '0004_alter_token_ttl'),
    ]

    operations = [
        migrations.CreateModel(
            name='GroupToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=64, unique=True)),
                ('ttl', models.IntegerField(default=30, help_text='Days till token expires')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='token', to='auth.group')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]