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
    logo = models.ImageField(upload_to='logos', blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True

    def get_absolute_primary_domain(self, request):
        http_type = 'https://' if request.is_secure() else 'http://'
        domain = get_current_site(request).domain
        return "".join([http_type, domain])



    def reverse(self, request, view_name, **kwargs):
        """
        Returns the URL of this tenant.
        """
        http_type = 'https://' if request.is_secure() else 'http://'

        domain = get_current_site(request).domain
        if self.domains.filter(is_primary=True).exists():
            url = ''.join((http_type, domain, reverse(view_name, kwargs=kwargs)))
        else:
            url = ''.join((http_type, self.schema_name, '.', domain, reverse(view_name, kwargs=kwargs)))

        return url


class Domain(DomainMixin):
    pass


class ClientSetting(models.Model):
    client = models.OneToOneField('Client', on_delete=models.CASCADE)
    default_from_email = models.EmailField(blank=True, null=True)
    email_host = models.CharField(max_length=1024, blank=True, null=True)
    email_host_password = models.CharField(max_length=1024, blank=True, null=True)
    email_host_user = models.CharField(max_length=1024, blank=True, null=True)
    email_port = models.PositiveSmallIntegerField(default=25)
    emaiL_use_tls = models.BooleanField(default=False)
    email_subject_prefix = models.CharField(max_length=1024, blank=True, null=True)
    

class ClientInfo(models.Model):
    client = models.OneToOneField('Client', on_delete=models.CASCADE)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=255, blank=True, null=True)
    contact_instagram = models.CharField(max_length=255, blank=True, null=True)
    contact_text = models.TextField(blank=True, null=True)
