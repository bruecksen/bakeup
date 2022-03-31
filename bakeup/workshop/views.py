from django.shortcuts import render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, DeleteView, UpdateView, TemplateView
from django_tables2 import SingleTableView

from bakeup.core.views import StaffPermissionsMixin
from bakeup.workshop.forms import ProductForm
from bakeup.workshop.models import Category, Product
from bakeup.workshop.tables import ProductTable



class WorkshopView(StaffPermissionsMixin, TemplateView):
    template_name = 'workshop/workshop.html'


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


class ProductListView(StaffPermissionsMixin, SingleTableView):
    model = Product
    table_class = ProductTable


class CategoryListView(StaffPermissionsMixin, ListView):
    model = Category


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.get_root_nodes()
        return context