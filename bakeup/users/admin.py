from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from bakeup.shop.models import Customer

from .models import Token, User


class CustomerInline(admin.StackedInline):
    model = Customer
    can_delete = False
    verbose_name_plural = "customer"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "date_joined",
        "is_staff",
    )
    inlines = (CustomerInline,)


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "created_at")
    fields = ("user", "token", "ttl", "created_at", "token_url", "qr_code_svg")
    readonly_fields = ("created_at", "token_url", "qr_code_svg")

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self.request = request
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.display(description="Token URL")
    def token_url(self, obj):
        return obj.token_url(self.request)

    @admin.display(description="QR Code")
    def qr_code_svg(self, obj):
        return obj.qr_code_svg(self.request)
