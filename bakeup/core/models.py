from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.db import models
from django.db.models import Manager
from django.db.models.enums import TextChoices
from django.template.loader import render_to_string
from django.urls import reverse
from django_tenants.models import DomainMixin, TenantMixin
from wagtail.models import Site
from wagtail.signal_handlers import disable_reference_index_auto_update

from bakeup.contrib.fields import ChoiceArrayField


class AbstractBaseManager(Manager):
    def get_queryset(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).filter(is_archived=False)

    def archived(self, *args, **kwargs):
        return super().get_queryset(*args, **kwargs).filter(is_archived=True)


class CommonBaseClass(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    objects = AbstractBaseManager()

    class Meta:
        abstract = True


class Client(TenantMixin):
    name = models.CharField(max_length=255)
    created = models.DateField(auto_now_add=True)
    logo = models.ImageField(upload_to="logos", blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    # default true, schema will be automatically created and synced when it is saved
    auto_create_schema = True
    wagtail_reference_index_ignore = True
    is_demo = models.BooleanField(default=False)

    def get_absolute_primary_domain(self, request):
        site = Site.find_for_request(request)
        return site.root_url

    @property
    def default_site(self):
        return Site.objects.get(is_default_site=True)

    @property
    def default_full_url(self):
        return self.default_site.root_url

    def reverse(self, request, view_name, **kwargs):
        """
        Returns the URL of this tenant.
        """
        http_type = "https://" if request.is_secure() else "http://"

        domain = get_current_site(request).domain
        if self.domains.filter(is_primary=True).exists():
            url = "".join((http_type, domain, reverse(view_name, kwargs=kwargs)))
        else:
            url = "".join(
                (
                    http_type,
                    self.schema_name,
                    ".",
                    domain,
                    reverse(view_name, kwargs=kwargs),
                )
            )

        return url

    def delete(self, force_drop=False, *args, **kwargs):
        """
        Deletes this row. Drops the tenant's schema if the attribute
        auto_drop_schema set to True.
        """
        self._drop_schema(force_drop)
        with disable_reference_index_auto_update():
            super().delete(*args, **kwargs)


class Domain(DomainMixin):
    wagtail_reference_index_ignore = True


class RegistrationFieldOption(TextChoices):
    FIRST_NAME = "first_name", "First name"
    LAST_NAME = "last_name", "Last name"
    POINT_OF_SALE = "point_of_sale", "Point of sale"
    STREET = "street", "Street"
    STREET_NUMBER = "street_number", "Street number"
    POSTAL_CODE = "postal_code", "Postal code"
    CITY = "city", "City"
    TELEPHONE_NUMBER = "telephone_number", "Telephone number"


def default_registration_fields():
    return ["first_name", "last_name", "point_of_sale"]


ACCOUNT_EMAIL_VERIFICATION_CHOICES = [
    ("optional", "optional"),
    ("mandatory", "mandatory"),
    ("none", "none"),
]


class ClientSetting(models.Model):
    client = models.OneToOneField("Client", on_delete=models.CASCADE)
    default_from_email = models.EmailField(blank=True, null=True)
    email_name = models.CharField(max_length=1024, blank=True, null=True)
    email_host = models.CharField(max_length=1024, blank=True, null=True)
    email_host_password = models.CharField(max_length=1024, blank=True, null=True)
    email_host_user = models.CharField(max_length=1024, blank=True, null=True)
    email_port = models.PositiveSmallIntegerField(blank=True, null=True)
    email_use_tls = models.BooleanField(default=False)
    show_full_name_delivery_bill = models.BooleanField(default=True)
    show_login = models.BooleanField(default=True)
    show_remaining_products = models.BooleanField(default=False)
    user_registration_fields = ChoiceArrayField(
        models.CharField(max_length=24, choices=RegistrationFieldOption.choices),
        default=default_registration_fields,
    )
    language_default = models.CharField(
        max_length=12, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE
    )
    account_email_verification = models.CharField(
        max_length=12, choices=ACCOUNT_EMAIL_VERIFICATION_CHOICES, default="optional"
    )
    is_newsletter_enabled = models.BooleanField(default=False)
    wagtail_reference_index_ignore = True


# TODO delete model, deprecated
class ClientInfo(models.Model):
    client = models.OneToOneField("Client", on_delete=models.CASCADE)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=255, blank=True, null=True)
    contact_instagram = models.CharField(max_length=255, blank=True, null=True)
    contact_text = models.TextField(blank=True, null=True)
    wagtail_reference_index_ignore = True


def get_production_day_reminder_body():
    return render_to_string(
        "users/emails/production_day_reminder_body.txt",
        {"client": "{{ client }}", "user": "{{ user }}", "order": "{{ order }}"},
    )


# TODO delete model after deployment, deprecated
class ClientEmailTemplate(models.Model):
    client = models.OneToOneField("Client", on_delete=models.CASCADE)
    production_day_reminder_subject = models.CharField(
        default="Deine Bestellung ist abholbereit", max_length=1024
    )
    production_day_reminder_body = models.TextField(
        default=get_production_day_reminder_body
    )
    wagtail_reference_index_ignore = True


class UOM(models.Model):
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)
    base_unit = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="units"
    )
    conversion_factor = models.FloatField(default=1.0)  # Factor to convert to base unit

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"

    @property
    def base_abbr(self):
        if self.base_unit:
            return self.base_unit.abbreviation
        return self.abbreviation

    def to_base_unit(self, value):
        return value * self.conversion_factor

    def from_base_unit(self, value):
        return value / self.conversion_factor
