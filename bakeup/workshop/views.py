from django.shortcuts import render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, DeleteView, UpdateView
from django_tables2 import SingleTableView

from bakeup.core.views import StaffPermissionsMixin
from bakeup.workshop.forms import ProductForm
from bakeup.workshop.models import Product
from bakeup.workshop.tables import ProductTable


class ProductAddView(StaffPermissionsMixin, CreateView):
    model = Product
    form_class = ProductForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class ProductUpdateView(StaffPermissionsMixin, UpdateView):
    model = Product
    form_class = ProductForm


class ProductDeleteView(StaffPermissionsMixin, DeleteView):
    model = Product

    def get_success_url(self):
        return reverse(
            'workshop:product-list',
        )
    

class ProductDetailView(StaffPermissionsMixin, DetailView):
    model = Product
    fields = ['name', 'description', 'image', 'categories', 'weight', 'weight_units', 'volume', 'volume_units', 'is_sellable', 'is_buyable', 'is_composable']


class ProductListView(StaffPermissionsMixin, SingleTableView):
    model = Product
    table_class = ProductTable
