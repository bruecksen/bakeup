from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.urls import reverse
from django.db.models.enums import TextChoices
from django.template.loader import render_to_string
from django.conf import settings

from django_tenants.models import TenantMixin, DomainMixin

from bakeup.contrib.fields import ChoiceArrayField


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


class RegistrationFieldOption(TextChoices):
    FIRST_NAME = 'first_name', "First name"
    LAST_NAME = 'last_name', "Last name"
    POINT_OF_SALE = 'point_of_sale', "Point of sale"
    STREET = 'street', "Street"
    STREET_NUMBER = 'street_number', "Street number"
    POSTAL_CODE = 'postal_code', "Postal code"
    CITY = 'city', "City"
    TELEPHONE_NUMBER = 'telephone_number', "Telephone number"

def default_registration_fields():
    return ['first_name', 'last_name', 'point_of_sale']


class ClientSetting(models.Model):
    client = models.OneToOneField('Client', on_delete=models.CASCADE)
    default_from_email = models.EmailField(blank=True, null=True)
    email_host = models.CharField(max_length=1024, blank=True, null=True)
    email_host_password = models.CharField(max_length=1024, blank=True, null=True)
    email_host_user = models.CharField(max_length=1024, blank=True, null=True)
    email_port = models.PositiveSmallIntegerField(default=25)
    emaiL_use_tls = models.BooleanField(default=False)
    show_full_name_delivery_bill = models.BooleanField(default=True)
    show_remaining_products = models.BooleanField(default=False)
    user_registration_fields = ChoiceArrayField(models.CharField(max_length=24, choices=RegistrationFieldOption.choices), default=default_registration_fields)
    language_default = models.CharField(max_length=12, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE)
    

class ClientInfo(models.Model):
    client = models.OneToOneField('Client', on_delete=models.CASCADE)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=255, blank=True, null=True)
    contact_instagram = models.CharField(max_length=255, blank=True, null=True)
    contact_text = models.TextField(blank=True, null=True)


def get_production_day_reminder_body():
    return render_to_string('users/emails/production_day_reminder_body.txt', {'client': '{{ client }}', 'user': '{{ user }}', 'order': '{{ order }}'})

class ClientEmailTemplate(models.Model):
    client = models.OneToOneField('Client', on_delete=models.CASCADE)
    production_day_reminder_subject = models.CharField(default='Deine Bestellung ist abholbereit', max_length=1024)
    production_day_reminder_body = models.TextField(default=get_production_day_reminder_body)
