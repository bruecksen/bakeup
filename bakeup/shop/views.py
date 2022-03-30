from datetime import datetime
from itertools import product

from django.views.generic import CreateView, DetailView, ListView, TemplateView, FormView
from django.shortcuts import render
from bakeup.contrib.calenderweek import CalendarWeek
from bakeup.core.views import CustomerRequiredMixin
from bakeup.shop.forms import CustomerOrderForm
from bakeup.shop.models import ProductionDay

from bakeup.workshop.models import Product


class ProductListView(CustomerRequiredMixin, ListView):
    model = Product


class WeeklyProductionDayView(CustomerRequiredMixin, FormView):
    template_name = 'shop/weekly.html'
    form_class = CustomerOrderForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar_week = None
        today = datetime.now().date()
        calendar_week_current = CalendarWeek(today.isocalendar()[1], datetime.now().date().year)
        if "calendar_week" in kwargs and "year" in kwargs:
            input_week = kwargs.get('calendar_week')
            input_year = kwargs.get('year')
            if 0 < input_week <= 53 and 2000 < input_year < 2050:
                calendar_week = CalendarWeek(input_week, input_year)
                if calendar_week != calendar_week_current:
                    context['calendar_week_current'] = calendar_week_current
        if calendar_week is None:
            calendar_week = calendar_week_current
        
        context['calendar_week'] = calendar_week
        qs = ProductionDay.objects.filter(day_of_sale__week=calendar_week.week, day_of_sale__year=calendar_week.year)
        production_days = dict()
        for production_day in qs:
            for production_day_product in production_day.production_day_products.filter(is_open_for_orders=True):
                form_initial = {
                    'production_day_id': production_day.pk,
                    'product_id': production_day_product.product.pk,
                }
                production_day_values = {
                    'production_day_product': production_day_product,
                    'form': CustomerOrderForm(initial=form_initial, prefix=f'production-day-{production_day_product.pk}')
                }
                production_days.setdefault(production_day.day_of_sale, []).append(production_day_values)
        # raise Exception(formsets)
        context['production_days'] = production_days
        return context



class ShopView(CustomerRequiredMixin, TemplateView):
    template_name = 'shop/shop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now().date()
        context['production_days'] = ProductionDay.objects.filter(is_open_for_orders=True, day_of_sale__gte=today)
        return context