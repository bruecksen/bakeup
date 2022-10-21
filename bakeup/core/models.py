from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.urls import reverse

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


    def reverse(self, request, view_name, **kwargs):
        """
        Returns the URL of this tenant.
        """
        http_type = 'https://' if request.is_secure() else 'http://'

        domain = get_current_site(request).domain

        url = ''.join((http_type, self.schema_name, '.', domain, reverse(view_name, kwargs=kwargs)))

        return url


class Domain(DomainMixin):
    pass
