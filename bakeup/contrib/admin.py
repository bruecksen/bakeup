from django.contrib import admin

from bakeup.contrib.models import Address, Note
from bakeup.core.admin import BaseAdmin


@admin.register(Address)
class AddressAdmin(BaseAdmin):
    list_display = ("address",)


@admin.register(Note)
class NoteAdmin(BaseAdmin):
    list_display = ("content", "user", "content_type", "object_id")
