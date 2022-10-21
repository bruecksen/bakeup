from django.contrib import admin

from django_tenants.admin import TenantAdminMixin

from bakeup.core.models import Client, Domain

# Register your models here.


class ExcludeAdminMixin(object):
    exclude = ('is_archived',)


@admin.register(Client)
class ClientAdmin(TenantAdminMixin, admin.ModelAdmin):
        list_display = ('name', 'created')


@admin.register(Domain)
class ClientAdmin(admin.ModelAdmin):
        list_display = ('domain', 'tenant', 'is_primary')