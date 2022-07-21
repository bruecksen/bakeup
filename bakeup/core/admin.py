from django.contrib import admin

from bakeup.core.models import Address

# Register your models here.


class ExcludeAdminMixin(object):
    exclude = ('is_archived',)


@admin.register(Address)
class AddressAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('address',)
