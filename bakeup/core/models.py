from django.db import models
from django_tenants.models import TenantMixin, DomainMixin


class CommonBaseClass(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Client(TenantMixin):
    name = models.CharField(max_length=255)
    created = models.DateField(auto_now_add=True)
    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True


class Domain(DomainMixin):
    pass
