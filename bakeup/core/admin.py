from django.contrib import admin
from django.forms.widgets import CheckboxSelectMultiple
from django_tenants.admin import TenantAdminMixin

from bakeup.contrib.fields import ChoiceArrayField
from bakeup.core.models import (
    Client,
    ClientEmailTemplate,
    ClientInfo,
    ClientSetting,
    Domain,
)

# Register your models here.


class BaseAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request) | self.model.objects.archived()


class ClientEmailTemplateInline(admin.StackedInline):
    model = ClientEmailTemplate


class ClientSettingInline(admin.StackedInline):
    model = ClientSetting
    formfield_overrides = {ChoiceArrayField: {"widget": CheckboxSelectMultiple}}


class ClientInfoInline(admin.StackedInline):
    model = ClientInfo


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
    inlines = (ClientSettingInline, ClientInfoInline, ClientEmailTemplateInline)
    list_display = ("name", "created")


@admin.register(Domain)
class ClientAdminDomain(admin.ModelAdmin):
    list_display = ("domain", "tenant", "is_primary")
