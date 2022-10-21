from django.db.models.signals import post_save
from django.dispatch import receiver

from bakeup.users.models import User, Token


@receiver(post_save, sender=User)
def create_user_token(sender, instance, created, **kwargs):
    if not hasattr(instance, 'token'):
        Token.objects.create(
            user=instance,
            token=Token.generate_token(),
        )