from django.contrib import admin

from django_tenants.admin import TenantAdminMixin

from bakeup.core.models import Client, Domain, ClientSetting

# Register your models here.


class ExcludeAdminMixin(object):
    exclude = ('is_archived',)


class ClientSettingInline(admin.StackedInline):
    model = ClientSetting

@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
        inlines = (ClientSettingInline, )
        list_display = ('name', 'created')


@admin.register(Domain)
class ClientAdminDomain(admin.ModelAdmin):
        list_display = ('domain', 'tenant', 'is_primary')