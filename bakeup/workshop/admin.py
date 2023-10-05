from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from bakeup.core.admin import ExcludeAdminMixin
from bakeup.workshop.models import (
    Category,
    Product,
    ProductHierarchy,
    ProductionPlan,
    ProductMapping,
    ProductPrice,
)


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    list_display = (
        "name",
        "slug",
        "image",
        "description",
    )
    form = movenodeform_factory(Category)


@admin.register(ProductHierarchy)
class ProductHierarchyAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ("parent", "child", "quantity")


@admin.register(Product)
class ProductAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ("name", "description", "product_template")


@admin.register(ProductPrice)
class ProductPriceAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ("product", "price")


@admin.register(ProductionPlan)
class ProductionPlanAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ("parent_plan", "product", "start_date", "quantity")
    list_filter = ("state", "production_day")


@admin.register(ProductMapping)
class ProductMappingAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = (
        "source_product",
        "target_product",
        "production_day",
        "matched_count",
    )
