from django.contrib import admin
from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from bakeup.core.admin import BaseAdmin
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
class ProductHierarchyAdmin(BaseAdmin):
    list_display = ("parent", "child", "quantity")


@admin.register(Product)
class ProductAdmin(BaseAdmin):
    list_display = ("name", "description", "product_template", "is_archived")
    list_filter = ("is_archived", "product_template")

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            | self.model.objects.archived()
            | self.model.objects.templates()
        )


@admin.register(ProductPrice)
class ProductPriceAdmin(admin.ModelAdmin):
    list_display = ("product", "price")


@admin.register(ProductionPlan)
class ProductionPlanAdmin(admin.ModelAdmin):
    list_display = ("parent_plan", "product", "start_date", "quantity")
    list_filter = ("state", "production_day")


@admin.register(ProductMapping)
class ProductMappingAdmin(admin.ModelAdmin):
    list_display = (
        "source_product",
        "target_product",
        "production_day",
        "matched_count",
    )
