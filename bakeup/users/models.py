from django.contrib.auth.models import AbstractUser
from django.db.models import CharField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import UserManager

from django_multitenant.mixins import TenantManagerMixin
from django_multitenant.models import TenantModel

from bakeup.tenants.models import Tenant
from bakeup.core.models import TenantModelMixin


class UserTenantManager(TenantManagerMixin, UserManager):
    pass


class User(AbstractUser):
    objects = UserTenantManager()

    def get_absolute_url(self):
        """Get url for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})
