from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _




class User(AbstractUser):

    def __str__(self):
        return self.get_full_name() or self.username

    def get_absolute_url(self):
        """Get url for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:profile")

    @property
    def is_customer(self):
        return hasattr(self, 'customer')
