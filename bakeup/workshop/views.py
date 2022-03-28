from django.shortcuts import render
from django.views.generic import CreateView, DetailView, ListView
from bakeup.core.views import StaffPermissionsMixin

from bakeup.workshop.forms import ProductAddForm
from bakeup.workshop.models import Product


class ProductAddView(StaffPermissionsMixin, CreateView):
    model = Product
    form_class = ProductAddForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_flagged'] = True
        return context


class ProductDetailView(StaffPermissionsMixin, DetailView):
    model = Product


class ProductListView(StaffPermissionsMixin, ListView):
    model = Product
