from django.contrib import admin

from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory
from bakeup.core.admin import ExcludeAdminMixin

from bakeup.workshop.models import Category, Product, ProductHierarchy, ProductionPlan


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    list_display = ('name', 'slug', 'image', 'description',)
    form = movenodeform_factory(Category)


@admin.register(ProductHierarchy)
class ProductHierarchyAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('parent', 'child', 'quantity')


@admin.register(Product)
class ProductAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'description', 'product_template')


@admin.register(ProductionPlan)
class ProductionPlanAdmin(ExcludeAdminMixin, admin.ModelAdmin):
    list_display = ('parent_plan', 'product', 'start_date', 'quantity')