from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.contrib.auth.models import Group
from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver

from bakeup.newsletter.models import Audience, Contact
from bakeup.shop.models import Customer, PointOfSale
from bakeup.users.models import GroupToken, Token, User


@receiver(post_save, sender=User)
def create_user_token(sender, instance, created, **kwargs):
    if not hasattr(instance, "token"):
        Token.objects.create(
            user=instance,
            token=Token.generate_token(),
        )


@receiver(post_save, sender=Group)
def create_group_token(sender, instance, created, **kwargs):
    if not hasattr(instance, "token"):
        GroupToken.objects.create(
            group=instance,
            token=GroupToken.generate_token(),
        )


@receiver(post_save, sender=User)
def create_user_customer(sender, instance, created, **kwargs):
    if not kwargs.get("raw", False) and not hasattr(instance, "customer"):
        point_of_sale = (
            PointOfSale.objects.all().count() == 1
            and PointOfSale.objects.first()
            or None
        )
        Customer.objects.create(
            user=instance,
            point_of_sale=point_of_sale,
        )
    client = connection.get_tenant()
    if not hasattr(instance, "contact") and client.clientsetting.is_newsletter_enabled:
        contact, created = Contact.objects.get_or_create(
            email__iexact=instance.email,
            defaults={
                "first_name": instance.first_name,
                "last_name": instance.last_name,
                "email": instance.email,
                "user": instance,
            },
        )
        contact.audiences.add(Audience.objects.filter(is_default=True).first())


@receiver(email_confirmed)
def update_user_email(sender, request, email_address, **kwargs):
    # Once the email address is confirmed, make new email_address primary.
    # This also sets user.email to the new email address.
    # email_address is an instance of allauth.account.models.EmailAddress
    email_address.set_as_primary()
    # Get rid of old email addresses
    EmailAddress.objects.filter(user=email_address.user).exclude(primary=True).delete()
    # Update users newsletter contact email
    if hasattr(email_address.user, "contact"):
        email_address.user.contact.email = email_address.email
        email_address.user.contact.save(update_fields=["email"])
