from django.db.models.signals import post_save
from django.dispatch import receiver

from bakeup.core.models import Client, ClientSetting


@receiver(post_save, sender=Client)
def create_user_customer(sender, instance, created, **kwargs):
    if not kwargs.get("raw", False) and not hasattr(instance, "clientsetting"):
        ClientSetting.objects.create(
            client=instance,
        )
