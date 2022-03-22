from django.db import models

from django_multitenant.models import TenantModel


class Tenant(TenantModel):
    tenant_id = 'id'
    name =  models.CharField(max_length=255)