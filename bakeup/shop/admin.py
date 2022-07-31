from django.contrib import admin

from bakeup.core.admin import ExcludeAdminMixin
from .models import Customer, CustomerOrder, CustomerOrderPosition, PointOfSale, PointOfSaleOpeningHour, ProductionDay, ProductionDayProduct, ProductionDayTemplate


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


@admin.register(ProductionDayProduct)
class ProductionDayProductAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('production_day', 'product', 'max_quantity')


@admin.register(ProductionDay)
class ProductionDayAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('day_of_sale',)


@admin.register(ProductionDayTemplate)
class ProductionDayAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('day_of_the_week', 'calendar_week', 'product', 'quantity')


@admin.register(CustomerOrderPosition)
class CustomerOrderPositionAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity')


class CustomerOrderPositionAdmin(ExcludeAdminMixin, admin.TabularInline):
    model = CustomerOrderPosition
    extra = 0


@admin.register(CustomerOrder)
class CustomerOrderAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('order_nr', 'production_day', 'customer', 'point_of_sale', 'address')
    inlines = (CustomerOrderPositionAdmin,)