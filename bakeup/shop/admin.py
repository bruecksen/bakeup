from django.contrib import admin

from bakeup.core.admin import BaseAdmin

from .models import (
    Customer,
    CustomerOrder,
    CustomerOrderPosition,
    CustomerOrderTemplate,
    CustomerOrderTemplatePosition,
    PointOfSale,
    PointOfSaleOpeningHour,
    ProductionDay,
    ProductionDayProduct,
    ProductionDayTemplate,
)


class PointOfSaleOpeningHourInline(admin.StackedInline):
    model = PointOfSaleOpeningHour
    extra = 0


@admin.register(PointOfSale)
class PointOfSaleAdmin(BaseAdmin):
    list_display = ("name", "is_primary", "address")
    inlines = (PointOfSaleOpeningHourInline,)


@admin.register(Customer)
class CustomerAdmin(BaseAdmin):
    list_display = (
        "user",
        "point_of_sale",
    )
    list_filter = ("point_of_sale",)
    search_fields = ("user__email", "point_of_sale__name")


@admin.register(ProductionDayProduct)
class ProductionDayProductAdmin(BaseAdmin):
    list_display = ("production_day", "product", "max_quantity")


@admin.register(ProductionDay)
class ProductionDayAdmin(BaseAdmin):
    list_display = ("day_of_sale",)


@admin.register(ProductionDayTemplate)
class ProductionDayTemplateAdmin(BaseAdmin):
    list_display = ("day_of_the_week", "calendar_week", "product", "quantity")


class CustomerOrderPositionAdmin(admin.TabularInline):
    model = CustomerOrderPosition
    extra = 0


@admin.register(CustomerOrder)
class CustomerOrderAdmin(BaseAdmin):
    list_display = (
        "order_nr",
        "production_day",
        "customer",
        "point_of_sale",
        "address",
        "created",
    )
    inlines = (CustomerOrderPositionAdmin,)
    search_fields = (
        "customer__user__email",
        "customer__user__first_name",
        "customer__user__last_name",
    )


class CustomerOrderTemplatePositionAdmin(admin.TabularInline):
    model = CustomerOrderTemplatePosition
    extra = 0


@admin.register(CustomerOrderTemplate)
class CustomerOrderTemplateAdmin(BaseAdmin):
    list_display = ("customer", "start_date", "end_date", "is_locked")
    inlines = (CustomerOrderTemplatePositionAdmin,)
