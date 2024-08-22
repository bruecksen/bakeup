from django.contrib import admin

from bakeup.core.admin import BaseAdmin
from bakeup.newsletter.models import Contact


@admin.register(Contact)
class ProductHierarchyAdmin(BaseAdmin):
    list_display = ("email", "first_name", "last_name", "is_active")
    list_filter = ("is_active", "user")
