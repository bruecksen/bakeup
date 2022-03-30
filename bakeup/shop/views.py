from datetime import datetime

from django.views.generic import CreateView, DetailView, ListView, TemplateView
from django.shortcuts import render
from bakeup.core.views import CustomerRequiredMixin
from bakeup.shop.models import ProductionDay

from bakeup.workshop.models import Product


class ProductListView(CustomerRequiredMixin, ListView):
    model = Product


class ShopView(CustomerRequiredMixin, TemplateView):
    template_name = 'shop/shop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now().date()
        context['production_days'] = ProductionDay.objects.filter(is_open_for_orders=True, day_of_sale__gte=today)
        return context