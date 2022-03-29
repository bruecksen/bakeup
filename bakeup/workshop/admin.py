from django.contrib import admin

from treebeard.admin import TreeAdmin
from treebeard.forms import movenodeform_factory

from bakeup.workshop.models import Category


@admin.register(Category)
class CategoryAdmin(TreeAdmin):
    list_display = ('name', 'slug', 'image', 'description',)
    form = movenodeform_factory(Category)
