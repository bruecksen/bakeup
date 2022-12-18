from datetime import datetime
from itertools import product
from django.forms import formset_factory
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.http import HttpResponseRedirect

from django.db.models import Q
from django.views.generic import CreateView, DetailView, ListView, TemplateView, FormView, DeleteView, UpdateView
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
        customer = None if self.request.user.is_anonymous else self.request.user.customer
        for production_day in production_days:
            production_day_products = []
            for production_day_product in production_day.production_day_products.all():
                form = production_day_product.get_order_form(customer)
                production_day_products.append({
                    'production_day_product': production_day_product,
                    'form': form
                })
            forms[production_day] = production_day_products
        
        context['production_days'] = forms
        return context


class CustomerOrderAddView(CustomerRequiredMixin, FormView):
    form_class = CustomerOrderForm
    http_method_names = ['post']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['production_day_product'] = self.production_day_product
        kwargs['customer'] = self.request.user.customer
        return kwargs

    def post(self, request, *args, **kwargs):
        self.production_day_product = get_object_or_404(ProductionDayProduct, pk=kwargs['production_day_product'])
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        created_order = CustomerOrder.create_or_update_customer_order_position(
            self.production_day_product.production_day,
            self.request.user.customer,
            self.production_day_product.product,
            form.cleaned_data["quantity"],
        )
        if created_order is None:
            messages.add_message(self.request, messages.INFO, "Bestellung erfolgreich gelöscht!")
        elif created_order:
            messages.add_message(self.request, messages.INFO, "Bestellung erfolgreich hinzugefügt!")
        else:
            messages.add_message(self.request, messages.INFO, "Bestellung wurde erfolgreich aktualisiert!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('shop:shop')

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.non_field_errors().as_text())
        return redirect(self.get_success_url())


class CustomerOrderAddBatchView(CustomerRequiredMixin, FormView):
    form_class = CustomerProductionDayOrderForm
    http_method_names = ['post']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['production_day_products'] = self.production_day.production_day_products.filter(is_published=True).filter(Q(production_plan__isnull=True) | Q(production_plan__state=0))
        kwargs['customer'] = self.request.user.customer
        return kwargs

    def post(self, request, *args, **kwargs):
        self.production_day = get_object_or_404(ProductionDay, pk=kwargs['production_day'])
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        created_order = CustomerOrder.create_or_update_customer_order(
            self.production_day,
            self.request.user.customer,
            form.product_quantity,
        )
        if created_order is None:
            messages.add_message(self.request, messages.INFO, "Bestellung erfolgreich gelöscht!")
        elif created_order:
            messages.add_message(self.request, messages.INFO, "Bestellung erfolgreich hinzugefügt!")
        else:
            messages.add_message(self.request, messages.INFO, "Bestellung wurde erfolgreich aktualisiert!")
        return super().form_valid(form)

    def get_success_url(self):
        return "{}#current-order".format(reverse('shop:shop'))

    def form_invalid(self, form):
        raise Exception(form)
        messages.add_message(self.request, messages.WARNING, form.non_field_errors().as_text())
        return redirect(self.get_success_url())


class CustomerOrderListView(CustomerRequiredMixin, SingleTableView):
    model = CustomerOrder
    template_name = 'shop/customer_order_list.html'
    table_class = CustomerOrderTable


    def get_queryset(self):
        return super().get_queryset().filter(customer=self.request.user.customer)


class CustomerOrderPositionDeleteView(CustomerRequiredMixin, DeleteView):
    model = CustomerOrderPosition

    def get_success_url(self):
        return "{}#current-order".format(reverse('shop:shop'))


class CustomerOrderPositionUpdateView(CustomerRequiredMixin, UpdateView):
    model = CustomerOrderPosition
    fields = ['quantity']

    def get_success_url(self):
        return "{}#current-order".format(reverse('shop:shop'))

    def form_valid(self, form):
        self.object = form.save()
        if self.object.quantity == 0:
            self.object.delete()
        return HttpResponseRedirect(self.get_success_url())



class ShopView(TemplateView):
    template_name = 'shop/shop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.now().date()
        production_day_next = ProductionDayProduct.objects.filter(is_published=True, production_day__day_of_sale__gte=today).order_by('production_day__day_of_sale').first()
        customer = None if self.request.user.is_anonymous else self.request.user.customer
        if production_day_next:
            context['production_day_next'] = production_day_next.production_day
            context['production_day_products'] = production_day_next.production_day.production_day_products.filter(is_published=True)
            context['current_customer_order'] = CustomerOrder.objects.filter(customer=customer, production_day=production_day_next.production_day).first()
            production_day_products = []
            for production_day_product in production_day_next.production_day.production_day_products.filter(is_published=True):
                form = production_day_product.get_order_form(customer)
                production_day_products.append({
                    'production_day_product': production_day_product,
                    'form': form
                })
            context['production_day_products'] = production_day_products
        return context



# class ProductListView(CustomerRequiredMixin, SingleTableView):
#     model = CustomerOrder
#     table_class = CustomerOrderTable
