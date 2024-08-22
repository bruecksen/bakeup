# Generated by Django 4.2.11 on 2024-08-22 20:10

from django.db import migrations

def create_contacts(apps, schema_editor):
    Contact = apps.get_model('newsletter', 'Contact')
    Audience = apps.get_model('newsletter', 'Audience')
    User = apps.get_model('users', 'User')
    for user in User.objects.filter(contact__isnull=True):
        Contact.objects.update_or_create(
            email__iexact=user.email,
            defaults={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "audience": Audience.objects.filter(is_default=True).first(),
                "user": user
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("newsletter", "0002_newsletterlistpage_content"),
    ]

    operations = [
        migrations.RunPython(create_contacts),
    ]
