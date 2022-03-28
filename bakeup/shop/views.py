from django.views.generic import CreateView, DetailView, ListView
from django.shortcuts import render
from bakeup.core.views import CustomerRequiredMixin

from bakeup.workshop.models import Product

# Create your views here.


class ProductListView(CustomerRequiredMixin, ListView):
    model = Product
