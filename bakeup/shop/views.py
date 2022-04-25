from datetime import datetime
from itertools import product
from django.forms import formset_factory
from django.urls import reverse

from django.views.generic import CreateView, DetailView, ListView, TemplateView, FormView
from django.shortcuts import get_object_or_404, render
from django_tables2 import SingleTableView
from bakeup.contrib.calenderweek import CalendarWeek
from bakeup.core.views import CustomerRequiredMixin
from bakeup.shop.forms import CustomerOrderForm, CustomerProductionDayOrderForm
from bakeup.shop.models import CustomerOrder, CustomerOrderPosition, ProductionDay

from bakeup.workshop.models import Product

# Limit orders in the future
MAX_FUTURE_ORDER_YEARS = 2

class ProductListView(CustomerRequiredMixin, ListView):
    model = Product


class WeeklyProductionDayView(CustomerRequiredMixin, TemplateView):
    template_name = 'shop/weekly.html'

    def get_calendar_week(self):
        if "calendar_week" in self.kwargs and "year" in self.kwargs:
            input_week = self.kwargs.get('calendar_week')
            input_year = self.kwargs.get('year')
            if 0 < input_week <= 53 and 2000 < input_year <= datetime.now().date().year + MAX_FUTURE_ORDER_YEARS:
                return CalendarWeek(input_week, input_year)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        calendar_week_current = CalendarWeek.current()
        calendar_week = self.get_calendar_week()
        if calendar_week and calendar_week != calendar_week_current:
            # only if we are showing a calender week that is not the current one
            # we need a jump to current link
            context['calendar_week_current'] = calendar_week_current
        if calendar_week is None:
            # fallback to current  week
            calendar_week = calendar_week_current
        context['calendar_week'] = calendar_week
        
        production_days = ProductionDay.objects.filter(day_of_sale__week=calendar_week.week, day_of_sale__year=calendar_week.year)
        forms = {}
        for production_day in production_days:
            production_day_products = []
            for production_day_product in production_day.production_day_products.all():
                form = production_day_product.get_order_form(self.request.user.customer)
                production_day_products.append({
                    'production_day_product': production_day_product,
                    'form': form
                })
            forms[production_day] = production_day_products
        
        context['production_days'] = forms
        return context


class AddCustomerOrderView(CustomerRequiredMixin, FormView):
    form_class = CustomerProductionDayOrderForm
    http_method_names = ['post']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['production_day_products'] = self.production_day.production_day_products.filter(is_open_for_orders=True)
        return kwargs

    def post(self, request, *args, **kwargs):
        self.production_day = get_object_or_404(ProductionDay, pk=kwargs['production_day'])
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        CustomerOrder.create_customer_order(
            self.production_day,
            self.request.user.customer,
            form.product_quantity,
        )
        return super().form_valid(form)

    def get_success_url(self):
        week = self.production_day.calendar_week
        year = self.production_day.year
        return reverse('shop:weekly', kwargs={'year': year, 'calendar_week': week})




class ShopView(CustomerRequiredMixin, TemplateView):
    template_name = 'shop/shop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now().date()
        context['production_days'] = ProductionDay.objects.filter(day_of_sale__gte=today)
        return context



# class ProductListView(CustomerRequiredMixin, SingleTableView):
#     model = CustomerOrder
#     table_class = CustomerOrderTable