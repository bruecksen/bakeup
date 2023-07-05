from datetime import datetime

from itertools import product
from typing import Any, Dict, List
from django.db.models.query import QuerySet
from django.forms import formset_factory
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.db.models import OuterRef, Subquery, Exists
from django.utils import timezone
from django.utils.timezone import make_aware

from django.db.models import F, Func, Value, CharField
from django.db.models.functions import Cast
from django.db.models import Q
from django.views.generic import CreateView, DetailView, ListView, TemplateView, FormView, DeleteView, UpdateView
from django.shortcuts import get_object_or_404, redirect, render

from django_tables2 import SingleTableView

from bakeup.contrib.calenderweek import CalendarWeek
from bakeup.core.views import CustomerRequiredMixin, StaffPermissionsMixin
from bakeup.shop.forms import CustomerOrderForm, CustomerProductionDayOrderForm
from bakeup.shop.models import Customer, CustomerOrder, CustomerOrderTemplate, CustomerOrderPosition, CustomerOrderTemplatePosition, ProductionDay, ProductionDayProduct, PointOfSale


from bakeup.workshop.models import Product
from bakeup.shop.tables import CustomerOrderTable

# Limit orders in the future
MAX_FUTURE_ORDER_YEARS = 2

class ProductListView(ListView):
    model = Product
    template_name = 'shop/product_list.html'

    def get_queryset(self) -> QuerySet[Any]:
        today = timezone.now().date()
        return Product.objects.filter(is_sellable=True, production_days__is_published=True, production_days__production_day__day_of_sale__gte=today).distinct().order_by('category')


class ProductionDayListView(ListView):
    model = ProductionDay
    template_name = 'shop/production_day_list.html'

    def get_queryset(self) -> QuerySet[Any]:
        return super().get_queryset().upcoming()


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
            if 0 < input_week <= 53 and 2000 < input_year <= timezone.now().date().year + MAX_FUTURE_ORDER_YEARS:
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
        return '/shop/'

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.non_field_errors().as_text())
        return redirect(self.get_success_url())


   

@login_required
def customer_order_add_or_update(request, production_day):
    if request.method == 'POST':
        production_day = get_object_or_404(ProductionDay, pk=production_day)
        products =  {Product.objects.get(pk=k.replace('product-', '')): int(v) for k, v in request.POST.items() if k.startswith('product-')}
        order = CustomerOrder.create_or_update_customer_order(
            production_day,
            request.user.customer,
            products,
            request.POST.get('point_of_sale', None)
        )
        products_recurring = {Product.objects.get(pk=k.replace('productabo-', '')): int(request.POST.get('product-{}'.format(k.replace('productabo-', '')))) for k, v in request.POST.items() if k.startswith('productabo-')}
        if products_recurring:
            order_template = CustomerOrderTemplate.create_customer_order_template(
                request,
                request.user.customer,
                products_recurring,
            )
        if order:
            return HttpResponseRedirect("{}#bestellung-{}".format(reverse('shop:order-list'), order.pk))
        else:
            return HttpResponseRedirect('/shop/')



class CustomerOrderListView(CustomerRequiredMixin, ListView):
    model = CustomerOrder
    template_name = 'shop/customer_order_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['point_of_sales'] = PointOfSale.objects.all()
        context['product_abos'] = {abo['product']: abo['quantity'] for abo in CustomerOrderTemplatePosition.objects.active().filter(order_template__customer=self.request.user.customer).values('product', 'quantity')}
        return context

    def get_queryset(self):
        return super().get_queryset().filter(customer=self.request.user.customer)


class CustomerOrderTemplateListView(CustomerRequiredMixin, ListView):
    model = CustomerOrderTemplate
    template_name = 'shop/customer_order_template_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['point_of_sales'] = PointOfSale.objects.all()
        return context

    def get_queryset(self):
        return super().get_queryset().active().filter(customer=self.request.user.customer)


class CustomerOrderPositionDeleteView(CustomerRequiredMixin, DeleteView):
    model = CustomerOrderPosition

    def get_success_url(self):
        return "{}#current-order".format('/shop/')


class CustomerOrderPositionUpdateView(CustomerRequiredMixin, UpdateView):
    model = CustomerOrderPosition
    fields = ['quantity']

    def get_success_url(self):
        return "{}#current-order".format('/shop/')

    def form_valid(self, form):
        self.object = form.save()
        if self.object.quantity == 0:
            self.object.delete()
        return HttpResponseRedirect(self.get_success_url())


class CustomerOrderUpdateView(CustomerRequiredMixin, UpdateView):
    model = CustomerOrder
    fields = ['point_of_sale']

    def get_success_url(self):
        return "/shop/#current-order"

    # def form_valid(self, form):
    #     self.object = form.save()
    #     return HttpResponseRedirect(self.get_success_url())


class CustomerOrderTemplateDeleteView(CustomerRequiredMixin, DeleteView):
    model = CustomerOrderTemplatePosition
    template_name = 'shop/customer_order_template_position_delete.html'

    def delete(self, request, *args, **kwargs):
        """
        Call the delete() method on the fetched object and then redirect to the
        success URL.
        """
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.cancel()
        return HttpResponseRedirect(success_url)
    

    def get_success_url(self):
        return reverse_lazy('shop:order-template-list')
    


@login_required
def customer_order_template_update(request, pk):
    if request.method == 'POST':
        customer_order_template = get_object_or_404(CustomerOrderTemplate, pk=pk)
        products_recurring = {Product.objects.get(pk=k.replace('productabo-', '')): int(request.POST.get('productabo-{}'.format(k.replace('productabo-', '')))) for k, v in request.POST.items() if k.startswith('productabo-')}
        if products_recurring:
            order_template = CustomerOrderTemplate.create_customer_order_template(
                request,
                request.user.customer,
                products_recurring,
            )
        return HttpResponseRedirect(reverse_lazy('shop:order-template-list'))




class ShopView(TemplateView):
    template_name = 'shop/shop.html'
    production_day = None

    def get_template_names(self) -> List[str]:
        if self.kwargs.get('production_day', None):
            return ['shop/production_day.html']
        else:
            return super().get_template_names()

    def setup(self, request, *args, **kwargs):
        self.production_day = self.get_production_day(*args, **kwargs)
        return super().setup(request, *args, **kwargs)

    def get_production_day(self, *args, **kwargs):
        if kwargs.get('production_day', None):
            return ProductionDay.objects.get(pk=kwargs.get('production_day'))
        else:
            today = timezone.now().date()
            production_day_next = ProductionDayProduct.objects.filter(
                is_published=True, 
                production_day__day_of_sale__gte=today).order_by('production_day__day_of_sale').first()
            if production_day_next:
                return production_day_next.production_day
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = None if self.request.user.is_anonymous else self.request.user.customer
        if self.production_day:
            context['production_day_next'] = self.production_day
            context['production_day_products'] = self.production_day.production_day_products.published()
            production_day_products = self.production_day.production_day_products.published()
            production_day_products = production_day_products.annotate(
                ordered_quantity=Subquery(CustomerOrderPosition.objects.filter(order__customer=customer, order__production_day=self.production_day, product=OuterRef('product__pk')).values("quantity"))
            ).annotate(
               has_abo=Exists(Subquery(CustomerOrderTemplatePosition.objects.active().filter(order_template__customer=customer, product=OuterRef('product__pk'))))
            )
            context['production_day_products'] = production_day_products
            context['current_customer_order'] = CustomerOrder.objects.filter(customer=customer, production_day=self.production_day).first()
        context['show_remaining_products'] = self.request.tenant.clientsetting.show_remaining_products
        context['point_of_sales'] = PointOfSale.objects.all()
        context['production_days'] = ProductionDay.objects.upcoming().exclude(id=self.production_day.pk)
        context['all_production_days'] = list(ProductionDay.objects.annotate(
            formatted_date=Func(
                F('day_of_sale'),
                Value('dd.MM.yyyy'),
                function='to_char',
                output_field=CharField()
            )
        ).values_list('formatted_date', flat=True))
        return context


# class ProductListView(CustomerRequiredMixin, SingleTableView):
#     model = CustomerOrder
#     table_class = CustomerOrderTable

def redirect_to_production_day_view(request):
    production_day_date = make_aware(datetime.strptime(request.POST.get('production_day_date', None), "%d.%m.%Y")).date()
    production_day = ProductionDay.objects.get(day_of_sale=production_day_date)
    return HttpResponseRedirect(reverse('shop:shop-production-day', kwargs={'production_day': production_day.pk}))