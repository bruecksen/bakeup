from datetime import datetime
from itertools import product
from django.forms import formset_factory
from django.urls import reverse

from django.views.generic import CreateView, DetailView, ListView, TemplateView, FormView
from django.shortcuts import get_object_or_404, render
from bakeup.contrib.calenderweek import CalendarWeek
from bakeup.core.views import CustomerRequiredMixin
from bakeup.shop.forms import CustomerOrderForm, CustomerProductionDayOrderForm
from bakeup.shop.models import CustomerOrder, CustomerOrderPosition, ProductionDay

from bakeup.workshop.models import Product


class ProductListView(CustomerRequiredMixin, ListView):
    model = Product


class WeeklyProductionDayView(CustomerRequiredMixin, TemplateView):
    template_name = 'shop/weekly.html'

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
        production_days = ProductionDay.objects.filter(day_of_sale__week=calendar_week.week, day_of_sale__year=calendar_week.year)
        forms = {}
        for production_day in production_days:
            production_day_products = []
            for production_day_product in production_day.production_day_products.all():
                quantity = 0
                existing_order = CustomerOrderPosition.objects.filter(product=production_day_product.product, order__production_day=production_day)
                if existing_order:
                    quantity = existing_order.first().quantity
                form = CustomerOrderForm(initial={'product': production_day_product.product.pk, 'quantity': quantity}, prefix=f'production_day_{production_day_product.product.pk}', production_day_product=production_day_product)
                production_day_products.append({
                    'production_day_product': production_day_product,
                    'form': form
                })
            forms[production_day] = production_day_products
        
        context['production_days'] = forms
        # raise Exception(forms)
        return context


class AddCustomerOrderView(CustomerRequiredMixin, FormView):
    form_class = CustomerProductionDayOrderForm
    http_method_names = ['post']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['production_day_products'] = self.production_day.production_day_products.all()
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
        context['production_days'] = ProductionDay.objects.filter(is_open_for_orders=True, day_of_sale__gte=today)
        return context