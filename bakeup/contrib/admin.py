from django.contrib import admin

from bakeup.contrib.models import Address, Note
from bakeup.core.admin import ExcludeAdminMixin


@admin.register(Address)
class AddressAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ("address",)


@admin.register(Note)
class NoteAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ("content", "user", "content_type", "object_id")
