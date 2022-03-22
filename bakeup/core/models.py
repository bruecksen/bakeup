from django.db import models

from django_multitenant.models import TenantModel as BaseTenantModel

from bakeup.tenants.models import Tenant


class TenantModel(BaseTenantModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    tenant_id = 'tenant_id'

    class Meta:
        abstract = True



class CommonBaseClass(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        abstract = True



# TODO: finish fields!
class Address(TenantModel):
    pass