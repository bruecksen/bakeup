from django.contrib import admin

from bakeup.core.admin import ExcludeAdminMixin
from .models import Customer, PointOfSale, PointOfSaleOpeningHour
from bakeup.core.models import Address


class PointOfSaleOpeningHourInline(ExcludeAdminMixin, admin.StackedInline):
    model = PointOfSaleOpeningHour
    extra = 0


@admin.register(PointOfSale)
class PointOfSaleAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'address')
    inlines = (PointOfSaleOpeningHourInline, )



@admin.register(Customer)
class CustomerAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('user', 'point_of_sale',)
    list_filter = ('point_of_sale',)
    search_fields = ('user__email', 'point_of_sale__name')
    
