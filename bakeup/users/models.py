from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import UserManager

from django_multitenant.mixins import TenantManagerMixin

from bakeup.core.models import TenantModel



class UserTenantManager(TenantManagerMixin, UserManager):
    pass


class User(AbstractUser, TenantModel):
    objects = UserTenantManager()

    def get_absolute_url(self):
        """Get url for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})
