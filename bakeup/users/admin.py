from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

from bakeup.shop.models import Customer

class CustomerInline(admin.StackedInline):
    model = Customer
    can_delete = False
    verbose_name_plural = 'customer'

class UserAdmin(BaseUserAdmin):
    inlines = (CustomerInline,)

admin.site.register(User, UserAdmin)