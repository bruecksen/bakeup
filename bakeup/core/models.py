from django.db import models

from django_multitenant.mixins import TenantModelMixin as BaseTenantModelMixin

from bakeup.tenants.models import Tenant


class TenantModelMixin(BaseTenantModelMixin):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    tenant_id = 'tenant_id'