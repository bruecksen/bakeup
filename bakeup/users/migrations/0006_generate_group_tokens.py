# Generated by Django 3.2.12 on 2022-10-21 08:53
import random
import string

from django.db import migrations

def generate_token():
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(random.choices(alphabet, k=8))

def make_tokens(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    GroupToken = apps.get_model('users', 'GroupToken')
    tokens = [GroupToken(group=group, token=generate_token(), ttl=30) for group in Group.objects.filter(token__isnull=True)]
    GroupToken.objects.bulk_create(tokens)

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_grouptoken'),
    ]

    operations = [
        migrations.RunPython(make_tokens),
    ]
