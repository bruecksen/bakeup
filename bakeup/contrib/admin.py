from django.contrib import admin

from bakeup.contrib.models import Address
from bakeup.core.admin import ExcludeAdminMixin


@admin.register(Address)
class AddressAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('address',)
