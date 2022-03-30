from django.contrib import admin

from bakeup.core.admin import ExcludeAdminMixin
from .models import Customer, PointOfSale, PointOfSaleOpeningHour, ProductionDay, ProductionDayTemplate
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


@admin.register(ProductionDay)
class ProductionDayAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('day_of_sale', 'product', 'max_quantity', 'is_open_for_orders')


@admin.register(ProductionDayTemplate)
class ProductionDayAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('day_of_the_week', 'calendar_week', 'product', 'quantity')
