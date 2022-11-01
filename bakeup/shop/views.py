from datetime import datetime
from itertools import product
from django.forms import formset_factory
from django.urls import reverse, reverse_lazy
from django.contrib import messages

from django.db.models import Q
from django.views.generic import CreateView, DetailView, ListView, TemplateView, FormView, DeleteView
from django.shortcuts import get_object_or_404, redirect, render

from django_tables2 import SingleTableView

from bakeup.contrib.calenderweek import CalendarWeek
from bakeup.core.views import CustomerRequiredMixin, StaffPermissionsMixin
from bakeup.shop.forms import CustomerOrderForm, CustomerProductionDayOrderForm
from bakeup.shop.models import Customer, CustomerOrder, CustomerOrderPosition, ProductionDay, ProductionDayProduct


from bakeup.workshop.models import Product
from bakeup.shop.tables import CustomerOrderTable

# Limit orders in the future
MAX_FUTURE_ORDER_YEARS = 2

class ProductListView(CustomerRequiredMixin, ListView):
    model = Product


class ProductionDayWeeklyView(CustomerRequiredMixin, TemplateView):
    template_name = 'shop/weekly.html'


    def dispatch(self, request, *args, **kwargs):
        self.calendar_week_current = CalendarWeek.current()
        self.calendar_week = self.get_calendar_week()
        if self.calendar_week is None:
            # fallback to current  week
            return redirect(reverse('shop:weekly', kwargs={'year': self.calendar_week_current.year, 'calendar_week': self.calendar_week_current.week}))
        return super().dispatch(request, *args, **kwargs)

    def get_calendar_week(self):
        if "calendar_week" in self.kwargs and "year" in self.kwargs:
            input_week = self.kwargs.get('calendar_week')
            input_year = self.kwargs.get('year')
            if 0 < input_week <= 53 and 2000 < input_year <= datetime.now().date().year + MAX_FUTURE_ORDER_YEARS:
                return CalendarWeek(input_week, input_year)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.calendar_week and self.calendar_week != self.calendar_week_current:
            # only if we are showing a calender week that is not the current one
            # we need a jump to current link
            context['calendar_week_current'] = self.calendar_week_current
        context['calendar_week'] = self.calendar_week
        
        production_days = ProductionDay.objects.filter(day_of_sale__week=self.calendar_week.week, day_of_sale__year=self.calendar_week.year)
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


class CustomerOrderAddView(CustomerRequiredMixin, FormView):
    form_class = CustomerProductionDayOrderForm
    http_method_names = ['post']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['production_day_products'] = self.production_day.production_day_products.filter(Q(production_plan__isnull=True) | Q(production_plan__state=0))
        kwargs['customer'] = self.request.user.customer
        return kwargs

    def post(self, request, *args, **kwargs):
        self.production_day = get_object_or_404(ProductionDay, pk=kwargs['production_day'])
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        created_order = CustomerOrder.create_customer_order(
            self.production_day,
            self.request.user.customer,
            form.product_quantity,
        )
        if created_order:
            messages.add_message(self.request, messages.INFO, "Bestellung erfolgreich hinzugefügt!")
        else:
            messages.add_message(self.request, messages.INFO, "Bestellung wurde erfolgreich aktualisiert!")
        return super().form_valid(form)

    def get_success_url(self):
        week = self.production_day.calendar_week
        year = self.production_day.year
        # return reverse('shop:weekly', kwargs={'year': year, 'calendar_week': week})
        return reverse('shop:shop')

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.non_field_errors().as_text())
        return redirect(self.get_success_url())


class CustomerOrderListView(CustomerRequiredMixin, SingleTableView):
    model = CustomerOrder
    template_name = 'shop/customer_order_list.html'
    table_class = CustomerOrderTable


    def get_queryset(self):
        return super().get_queryset().filter(customer=self.request.user.customer)


class ShopView(CustomerRequiredMixin, TemplateView):
    template_name = 'shop/shop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now().date()
        production_day_next = ProductionDay.objects.filter(day_of_sale__gte=today).first()
        context['production_day_next'] = production_day_next
        if production_day_next:
            production_day_products = []
            for production_day_product in production_day_next.production_day_products.all():
                form = production_day_product.get_order_form(self.request.user.customer)
                production_day_products.append({
                    'production_day_product': production_day_product,
                    'form': form
                })
            context['production_day_products'] = production_day_products
        return context



# class ProductListView(CustomerRequiredMixin, SingleTableView):
#     model = CustomerOrder
#     table_class = CustomerOrderTable
