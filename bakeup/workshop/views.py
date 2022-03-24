from django.shortcuts import render
from django.views.generic import CreateView, DetailView, ListView

from django_multitenant.utils import get_current_tenant

from bakeup.workshop.forms import ProductAddForm
from bakeup.workshop.models import Product

# Create your views here.


class ProductAddView(CreateView):
    model = Product
    form_class = ProductAddForm
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_flagged'] = True
        context['tenant'] = get_current_tenant()
        return context


class ProductDetailView(DetailView):
    model = Product


class ProductListView(ListView):
    model = Product
