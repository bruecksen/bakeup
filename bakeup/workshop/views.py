import copy
from itertools import repeat
from itertools import product
from typing import Any, OrderedDict
from django import http
from django.db.models.query import QuerySet

from django.utils.timezone import now
from django.core.mail import send_mass_mail
from django.utils.datastructures import MultiValueDict
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.contrib import messages
from django.db.models import Q, F
from django.http import Http404, HttpRequest, HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import resolve, reverse, reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import RedirectView, CreateView, DetailView, ListView, DeleteView, UpdateView, TemplateView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormMixin
from django.db.models import Sum
from django.utils.timezone import make_aware
from django.conf import settings
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView

from django_htmx.http import HttpResponseClientRefresh
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView
from django_tables2.export import ExportMixin as TableExportMixin
import django_tables2 as tables
from treebeard.forms import movenodeform_factory

from bakeup.workshop.templatetags.workshop_tags import clever_rounding 
from bakeup.core.views import StaffPermissionsMixin, NextUrlMixin
from bakeup.core.utils import get_deleted_objects
from bakeup.shop.forms import BatchCustomerOrderFormSet, BatchCustomerOrderTemplateFormSet, CustomerOrderPositionFormSet, CustomerProductionDayOrderForm, ProductionDayProductFormSet, ProductionDayForm
from bakeup.shop.models import Customer, CustomerOrder, CustomerOrderPosition, ProductionDay, ProductionDayProduct, PointOfSale, CustomerOrderTemplate, CustomerOrderTemplatePosition
from bakeup.workshop.forms import AddProductForm, AddProductFormSet, ProductForm, ProductHierarchyForm, ProductKeyFiguresForm, ProductionPlanDayForm, ProductionPlanForm, SelectProductForm, SelectProductionDayForm, CustomerForm, ProductionDayMetaProductformSet, ProductionDayReminderForm, ReminderMessageForm, SelectReminderMessageForm
from bakeup.workshop.models import Category, Product, ProductPrice, ProductHierarchy, ProductionPlan, Instruction, ProductMapping, ReminderMessage
from bakeup.workshop.tables import PointOfSaleTable, CustomerOrderFilter, CustomerOrderTable, CustomerTable, CustomerFilter, ProductFilter, ProductTable, ProductionDayTable, ProductionPlanFilter, ProductionPlanTable
from bakeup.workshop.export import ExportMixin
from bakeup.users.models import User
from bakeup.pages.models import EmailSettings


class WorkshopView(StaffPermissionsMixin, TemplateView):
    template_name = 'workshop/workshop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recipies_count'] = Product.objects.filter(is_sellable=True).count()
        context['products_count'] = Product.objects.all().count()
        context['categories_count'] = Category.objects.all().count()
        context['productionplans_count'] = ProductionPlan.objects.all().count()
        context['productiondays_count'] = ProductionDay.objects.all().count()
        return context


class ProductAddView(StaffPermissionsMixin, CreateView):
    model = Product
    form_class = ProductForm
    form_select_class = SelectProductForm
    product_parent = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_select'] = SelectProductForm()
        context['product_parent'] = self.product_parent
        return context

    def dispatch(self, request, *args, **kwargs):
        if 'pk' in kwargs:
            self.product_parent = get_object_or_404(Product, pk=self.kwargs.get('pk'))
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if 'add-existing' in request.POST:
            form = SelectProductForm(request.POST)
            if form.is_valid():
                product = form.cleaned_data['product']
                self.object = self.product_parent
                self.product_parent.add_child(product)
            return HttpResponseRedirect(self.get_success_url())
        elif 'add-new' in request.POST:
            return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        product = form.save()
        price = form.cleaned_data['price']
        if price:
            price, created = ProductPrice.objects.update_or_create(
                product=product,
                defaults={"price": price},
            )
        self.object = product
        if self.product_parent:
            self.product_parent.add_child(product)
        return HttpResponseRedirect(self.get_success_url())

@staff_member_required(login_url='login')
def product_add_inline_view(request, pk):
    parent_product = Product.objects.get(pk=pk)
    if request.method == 'POST':
        formset = AddProductFormSet(request.POST)
        if formset.is_valid():
            for form in formset:
                product = None
                quantity = None
                if form.cleaned_data.get('product_existing', None) and form.cleaned_data.get('weight', None):
                    product = form.cleaned_data['product_existing']
                    if parent_product.has_child(product):
                        product = None
                        messages.add_message(request, messages.WARNING, "This product is already a child product.")
                    if parent_product == product:
                        product = None
                        messages.add_message(request, messages.WARNING, "You cannot add the parent product as a child product again")
                    quantity =  form.cleaned_data.get('weight', 1000) / product.weight
                if form.cleaned_data.get('product_new', None) and form.cleaned_data.get('category', None):
                    product = Product.objects.create(
                        name=form.cleaned_data['product_new'],
                        category=form.cleaned_data['category'],
                        weight=1000,
                        is_sellable=form.cleaned_data.get('is_sellable', False),
                        is_buyable=form.cleaned_data.get('is_buyable', False),
                        is_composable=form.cleaned_data.get('is_composable', False),
                    )
                    quantity =  form.cleaned_data.get('weight', 1000) / product.weight
                if product and quantity:
                    parent_product.add_child(product, quantity)
        else:
            raise Exception(formset.errors)
    return HttpResponseRedirect(reverse('workshop:product-detail', kwargs={'pk': parent_product.pk}))


class ProductUpdateView(StaffPermissionsMixin, UpdateView):
    model = Product
    form_class = ProductForm

    def form_valid(self, form):
        product = form.save()
        price = form.cleaned_data['price']
        if price:
            price, created = ProductPrice.objects.update_or_create(
                product=product,
                defaults={"price": price},
            )
        self.object = product
        return HttpResponseRedirect(self.get_success_url())


class ProductDeleteView(StaffPermissionsMixin, DeleteView):
    model = Product

    def get_success_url(self):
        return reverse(
            'workshop:product-list',
        )


class ProductHierarchyDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductHierarchy

    def get_success_url(self):
        return reverse('workshop:product-detail', kwargs={'pk': self.object.parent.pk})


class ProductHierarchyUpdateView(StaffPermissionsMixin, FormView):
    model = ProductHierarchy
    form_class = ProductHierarchyForm

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(ProductHierarchy, pk=kwargs.get('pk'))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        amount = form.cleaned_data['amount']
        if amount and self.object.child.weight:
            self.object.quantity =  amount / self.object.child.weight
            self.object.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        raise Exception(form.errors)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse('workshop:product-detail', kwargs={'pk': self.object.parent.pk})


class ProductDetailView(StaffPermissionsMixin, DetailView):
    model = Product

    def get_key_figures_inital_data(self):
        return {
            'fermentation_loss': clever_rounding(self.object.get_fermentation_loss()),
            'dough_yield': self.object.get_dough_yield(),
            'salt': clever_rounding(self.object.get_salt_ratio()),
            'starter': self.object.get_starter_ratio(),
            'wheat': self.object.get_wheats(),
            'pre_ferment': clever_rounding(self.object.get_pre_ferment_ratio()),
            'total_dough_weight': clever_rounding(self.object.total_weight),
        }


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = AddProductFormSet(form_kwargs={'parent_products': self.object.childs.with_weights(), 'product': self.object})
        if self.object.is_composable:
            context['key_figures_form'] = ProductKeyFiguresForm(initial=self.get_key_figures_inital_data())
        return context


def product_normalize_view(request, pk):
    product = Product.objects.get(pk=pk)
    if request.method == 'POST':
        form = ProductKeyFiguresForm(request.POST)
        if form.is_valid():
            fermentation_loss = form.cleaned_data['fermentation_loss']
            product.normalize(fermentation_loss)
        else:
            raise Exception(form.errors)
    return redirect(product.get_absolute_url())


class RecipeDetailView(StaffPermissionsMixin, DetailView):
    model = Product
    template_name = 'workshop/recipe_detail.html'

    def get_context_data(self, **kwargs):
        # raise Exception(self.object.parents.all())
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(is_sellable=True)
        return qs



class RecipeListView(StaffPermissionsMixin, SingleTableMixin, FilterView):
    model = Product
    table_class = ProductTable
    filterset_class = ProductFilter
    template_name = 'workshop/product_list.html'

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(is_sellable=True)
        return qs

class ProductListView(StaffPermissionsMixin, SingleTableMixin, FilterView):
    model = Product
    table_class = ProductTable
    filterset_class = ProductFilter
    template_name = 'workshop/product_list.html'


@staff_member_required(login_url='login')
def production_plan_redirect_view(request):
    if request.method == 'POST':
        form = ProductionPlanDayForm(request.POST)
        if form.is_valid():
            url = reverse('workshop:production-plan-production-day', kwargs={'pk': form.cleaned_data['production_day'].pk})
    else:
        production_day = ProductionDay.objects.upcoming().first()
        if not production_day:
            production_day = ProductionDay.objects.all().first()
        if production_day:
            url = reverse('workshop:production-plan-production-day', kwargs={'pk': production_day.pk})
        else:
            url = reverse('workshop:production-plan-list')
    return HttpResponseRedirect(url)


class ProductionPlanOfProductionDay(StaffPermissionsMixin, ListView):
    model = ProductionPlan
    context_object_name = 'production_plans'
    template_name = 'workshop/productionplan_productionday.html'
    ordering = ('-production_day', 'product__name')
    production_day = None

    def setup(self, request, *args, **kwargs):
        self.production_day = ProductionDay.objects.get(pk=kwargs['pk'])
        return super().setup(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(parent_plan__isnull=True, production_day=self.production_day)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table_categories = OrderedDict()
        for category in ProductionPlan.objects.filter(parent_plan__isnull=False).order_by('pk').values_list('product__category__name', flat=True):
            if not category in table_categories:
                table_categories[category] = {
                }
        production_plans = []
        for production_plan in context['production_plans']:
            plan_dict = OrderedDict()
            plan_dict['root'] = production_plan
            for child in ProductionPlan.objects.filter(
                Q(parent_plan=production_plan) | 
                Q(parent_plan__parent_plan=production_plan) | 
                Q(parent_plan__parent_plan__parent_plan=production_plan) |
                Q(parent_plan__parent_plan__parent_plan__parent_plan=production_plan)):
                    plan_dict.setdefault(child.product.category.name, [])
                    plan_dict[child.product.category.name].append(child)
            production_plans.append(plan_dict)
        context['table_categories'] = table_categories
        context['production_plans'] = production_plans
        context['production_day'] = self.production_day
        context['production_day_form'] = ProductionPlanDayForm(initial={'production_day': self.production_day})
        try:
            context['production_day_prev'] = ProductionDay.get_previous_by_day_of_sale(self.production_day)
        except:
            pass
        try:
            context['production_day_next'] = ProductionDay.get_next_by_day_of_sale(self.production_day)
        except:
            pass
        context['has_plans_to_start'] = self.get_queryset().filter(state=ProductionPlan.State.PLANNED).exists()
        context['has_plans_to_finish'] = self.get_queryset().filter(state=ProductionPlan.State.IN_PRODUCTION).exists()
        return context



class ProductionPlanListView(StaffPermissionsMixin, FilterView):
    model = ProductionPlan
    context_object_name = 'production_plans'
    filterset_class = ProductionPlanFilter
    template_name = 'workshop/productionplan_list.html'
    ordering = ('-production_day', 'product__name')

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(parent_plan__isnull=True)

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        if kwargs['data'] is None:
            filter_values = MultiValueDict()
        else:
            filter_values = kwargs['data'].copy()

        if not filter_values:
            # we need to use `setlist` for multi-valued fields to emulate this coming from a query dict
            filter_values.setlist('state', ['0', '1'])
        
        kwargs['data'] = filter_values
        return kwargs

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table_categories = OrderedDict()
        for category in ProductionPlan.objects.filter(parent_plan__isnull=False).order_by('pk').values_list('product__category__name', flat=True):
            if not category in table_categories:
                table_categories[category] = {
                }
        production_plans = []
        for production_plan in context['production_plans']:
            plan_dict = OrderedDict()
            plan_dict['root'] = production_plan
            for child in ProductionPlan.objects.filter(
                Q(parent_plan=production_plan) | 
                Q(parent_plan__parent_plan=production_plan) | 
                Q(parent_plan__parent_plan__parent_plan=production_plan) |
                Q(parent_plan__parent_plan__parent_plan__parent_plan=production_plan)):
                    plan_dict.setdefault(child.product.category.name, [])
                    plan_dict[child.product.category.name].append(child)
            production_plans.append(plan_dict)
        context['table_categories'] = table_categories
        context['production_plans'] = production_plans
        context['day_of_sale_selected'] = context['filter'].form.cleaned_data.get('production_day') or ''
        return context


class ProductionPlanDetailView(StaffPermissionsMixin, DetailView):
    model = ProductionPlan


class ProductionPlanAddView(StaffPermissionsMixin, FormView):
    model = ProductionPlan
    form_class = ProductionPlanDayForm
    template_name = 'workshop/production_plan_form.html'

    def form_valid(self, form):
        production_day = form.cleaned_data['production_day']
        self.production_day = production_day 
        if production_day:
            production_day.create_production_plans(create_max_quantity=True)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('workshop:production-plan-production-day', kwargs={'pk': self.production_day.pk})


@staff_member_required(login_url='login')
def production_plan_update(request, production_day, product):
    product = Product.objects.get(pk=product)
    production_day = ProductionDay.objects.get(pk=production_day)
    production_day.update_production_plan(filter_product=product, create_max_quantity=False)
    return HttpResponseRedirect(reverse('workshop:production-plan-production-day', kwargs={'pk': production_day.pk}))


@staff_member_required(login_url='login')
def production_plan_next_state_view(request, pk):
    production_plan = ProductionPlan.objects.get(pk=pk)
    production_day = production_plan.production_day
    product = production_plan.product.product_template
    if production_plan.get_next_state() == ProductionPlan.State.IN_PRODUCTION:
        production_plan.production_day.update_production_plan(filter_product=production_plan.product.product_template, create_max_quantity=False)
    if ProductionPlan.objects.filter(production_day=production_day, product__product_template=product).exists():
        production_plan = ProductionPlan.objects.get(production_day=production_day, product__product_template=product)
        production_plan.set_next_state()
    return HttpResponseRedirect(reverse('workshop:production-plan-production-day', kwargs={'pk': production_plan.production_day.pk}))


@staff_member_required(login_url='login')
def production_plans_start_view(request, production_day):
    production_day = ProductionDay.objects.get(pk=production_day)
    production_plans = ProductionPlan.objects.filter(production_day=production_day, state=ProductionPlan.State.PLANNED, parent_plan__isnull=True)
    for production_plan in production_plans:
        production_plan.production_day.update_production_plan(filter_product=production_plan.product.product_template, create_max_quantity=False)
    production_plans = ProductionPlan.objects.filter(production_day=production_day, state=ProductionPlan.State.PLANNED, parent_plan__isnull=True)
    for production_plan in production_plans:
        production_plan.set_production()
        production_plan.production_day.update_order_positions_product(production_plan.product)
        production_plan.set_production()
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET.get('next'))
    return HttpResponseRedirect(reverse('workshop:production-plan-next'))


@staff_member_required(login_url='login')
def production_plan_start_view(request, pk):
    production_plan = ProductionPlan.objects.get(pk=pk)

    if production_plan.get_next_state() == ProductionPlan.State.IN_PRODUCTION:
        production_plan = production_plan.production_day.update_production_plan(filter_product=production_plan.product.product_template, create_max_quantity=False)
        production_plan.set_production()
        production_plan.production_day.update_order_positions_product(production_plan.product)
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET.get('next'))
    return HttpResponseRedirect(reverse('workshop:production-plan-production-day', kwargs={'pk': production_plan.production_day.pk}))


@staff_member_required(login_url='login')
def production_plans_finish_view(request, production_day):
    production_day = ProductionDay.objects.get(pk=production_day)
    production_plans = ProductionPlan.objects.filter(
        production_day=production_day, 
        state=ProductionPlan.State.IN_PRODUCTION, 
        parent_plan__isnull=True)
    production_plans.update(
        state=ProductionPlan.State.PRODUCED
    )
    if 'next' in request.GET:
        return HttpResponseRedirect(request.GET.get('next'))
    return HttpResponseRedirect(reverse('workshop:production-plan-next'))


@staff_member_required(login_url='login')
def production_plan_cancel_view(request, pk):
    production_plan = ProductionPlan.objects.get(pk=pk)
    production_plan.set_state(ProductionPlan.State.CANCELED)
    return HttpResponseRedirect(reverse('workshop:production-plan-production-day', kwargs={'pk': production_plan.production_day.pk}))


@require_POST
@staff_member_required(login_url='login')
def customer_order_toggle_picked_up_view(request, pk):
    customer_order = CustomerOrder.objects.get(pk=pk)
    customer_order.positions.all().update(is_picked_up=not customer_order.is_picked_up)
    return HttpResponse()


@staff_member_required(login_url='login')
def customer_order_all_picked_up_view(request, pk):
    CustomerOrderPosition.objects.filter(order__production_day=pk).update(is_picked_up=True)
    return HttpResponseRedirect("{}#orders".format(reverse('workshop:production-day-detail', kwargs={'pk': pk})))

@staff_member_required(login_url='login')
def pos_order_all_picked_up_view(request, production_day, pos):
    CustomerOrderPosition.objects.filter(order__production_day=production_day, order__point_of_sale=pos).update(is_picked_up=True)
    return HttpResponseClientRefresh()


class ProductionPlanDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductionPlan


    def get_success_url(self):
        return reverse('workshop:production-plan-next')


class CategoryListView(StaffPermissionsMixin, ListView):
    model = Category


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.get_root_nodes()
        return context
    

class CategoryAddView(StaffPermissionsMixin, CreateView):
    model = Category
    form_class = movenodeform_factory(model, exclude=['slug', 'image', 'description', 'is_archived'])
    success_url = reverse_lazy('workshop:category-list')


class CategoryUpdateView(StaffPermissionsMixin, UpdateView):
    model = Category
    form_class = movenodeform_factory(model, exclude=['slug', 'image', 'description', 'is_archived'])
    success_url = reverse_lazy('workshop:category-list')


class CategoryDeleteView(StaffPermissionsMixin, DeleteView):
    model = Category
    success_url = reverse_lazy('workshop:category-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        context['deletable_objects'] = deletable_objects
        context['model_count'] = dict(model_count).items()
        context['protected'] = protected
        return context


class CustomerOrderUpdateView(StaffPermissionsMixin, UpdateView):
    model = CustomerOrder
    fields = ['point_of_sale']
    template_name = "workshop/customerorder_form.html"
    success_url = reverse_lazy('workshop:order-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = CustomerOrderPositionFormSet(self.request.POST, form_kwargs={'production_day_products': Product.objects.filter(production_days__production_day=self.object.production_day)})
        else:
            context['formset'] = CustomerOrderPositionFormSet(queryset=self.object.positions.all(), form_kwargs={'production_day_products': Product.objects.filter(production_days__production_day=self.object.production_day)})
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        formset = CustomerOrderPositionFormSet(request.POST)
        form = self.get_form()
        if formset.is_valid() and form.is_valid():
            return self.form_valid(form, formset)
        else:
            return self.form_invalid(form, formset)

    def form_valid(self, form, formset):
        with transaction.atomic():
            form.save()
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for instance in instances:
                instance.order = self.object
                instance.save()
        return HttpResponseRedirect(reverse('workshop:order-list'))

    def form_invalid(self, form, formset):
        raise Exception(form.errors, formset.errors)
        return self.render_to_response(self.get_context_data())

@staff_member_required(login_url='login')
def production_day_redirect_view(request):
    if request.method == 'POST':
        form = ProductionPlanDayForm(request.POST)
        if form.is_valid():
            url = reverse('workshop:production-day-detail', kwargs={'pk': form.cleaned_data['production_day'].pk})
    else:
        production_day = ProductionDay.objects.upcoming().first()
        if not production_day:
            production_day = ProductionDay.objects.all().first()
        if production_day:
            url = reverse('workshop:production-day-detail', kwargs={'pk': production_day.pk})
        else:
            url = reverse('workshop:production-day-add')
    return HttpResponseRedirect(url)


class ProductionDayListView(StaffPermissionsMixin, SingleTableView):
    model = ProductionDay
    table_class = ProductionDayTable
    template_name = "workshop/productionday_list.html"


class ProductionDayDetailView(StaffPermissionsMixin, DetailView):
    model = ProductionDay
    template_name = "workshop/productionday_detail.html"


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        point_of_sales = []
        for point_of_sale in PointOfSale.objects.filter(customer_orders__production_day=self.object).distinct():
            positions = CustomerOrderPosition.objects.exclude(
                Q(production_plan__state=ProductionPlan.State.CANCELED) |
                Q(production_plan__state__isnull=True)
            ).filter(
                order__point_of_sale=point_of_sale, 
                order__production_day=self.object
            )
            order_summary = positions.values('product__name').annotate(quantity=Sum('quantity'))
            point_of_sales.append({
                'point_of_sale': point_of_sale,
                'orders': CustomerOrder.objects.filter(pk__in=positions.values_list('order', flat=True)).order_by('customer__user__last_name'),
                'summary': order_summary,
                'all_picked_up': not CustomerOrderPosition.objects.filter(order__production_day=self.object, order__point_of_sale=point_of_sale, is_picked_up=False).exists()
            })
        # raise Exception(point_of_sales)
        context['point_of_sales'] = point_of_sales
        context['production_day_form'] = ProductionPlanDayForm(initial={'production_day': self.object})
        try:
            context['production_day_prev'] = ProductionDay.get_previous_by_day_of_sale(self.object)
        except:
            pass
        try:
            context['production_day_next'] = ProductionDay.get_next_by_day_of_sale(self.object)
        except:
            pass
        context['has_plans_to_start'] = ProductionPlan.objects.filter(production_day=self.object, state=ProductionPlan.State.PLANNED, parent_plan__isnull=True).exists()
        context['has_plans_to_finish'] = ProductionPlan.objects.filter(production_day=self.object, state=ProductionPlan.State.IN_PRODUCTION, parent_plan__isnull=True).exists()
        return context

#
class ProductionDayMixin(object):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = ProductionDayProductFormSet(self.request.POST)
            context['form'] = ProductionDayForm(instance=self.object, data=self.request.POST)
        else:
            production_day_products = ProductionDayProduct.objects.filter(production_day=self.object)
            context['formset'] = ProductionDayProductFormSet(queryset=production_day_products)
            if self.object and production_day_products.count() > 0:
                context['formset'].extra = 0
            context['form'] = ProductionDayForm(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        formset = ProductionDayProductFormSet(request.POST)
        production_day_form = ProductionDayForm(instance=self.object, data=request.POST)
        if formset.is_valid() and production_day_form.is_valid():
            return self.form_valid(formset, production_day_form)
        else:
            return self.form_invalid(production_day_form, formset)

    def form_valid(self, formset, production_day_form):
        with transaction.atomic():
            production_day = production_day_form.save()
            self.object = production_day
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                try:
                    obj.delete()
                except ProtectedError as e:
                    messages.error(self.request, e)
            for instance in instances:
                instance.production_day = production_day
                instance.save()
        production_day.create_template_orders(self.request)
        production_day.create_production_plans(create_max_quantity=True)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form, formset):
        if form.errors:
            messages.error(self.request, form.errors)
        for form_error in formset.errors:
            if form_error:
                messages.error(self.request, form_error)
        if formset.non_form_errors():
            messages.error(self.request, formset.non_form_errors())
        return self.render_to_response(self.get_context_data())
    
    def get_success_url(self):
        return reverse(
            'workshop:production-day-next',
        )


class ProductionDayAddView(NextUrlMixin, ProductionDayMixin, CreateView):
    template_name = "workshop/productionday_form.html"
    model =  ProductionDay
    form_class = ProductionDayForm

    def get_object(self, queryset=None):
        return None


class ProductionDayUpdateView(NextUrlMixin, ProductionDayMixin, UpdateView):
    template_name = "workshop/productionday_form.html"
    model =  ProductionDay
    form_class = ProductionDayForm


class ProductionDayDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductionDay
    template_name = 'workshop/productionday_confirm_delete.html'

    def get_object(self):
        object = super().get_object()
        if object.is_locked:
            raise Http404()
        return object

    def get_success_url(self):
        return reverse(
            'workshop:production-day-next',
        )
    
@staff_member_required(login_url='login')
def reminder_message_redirect_view(request, pk):
    production_day = ProductionDay.objects.get(pk=pk)
    if request.method == 'POST':
        form = SelectReminderMessageForm(request.POST, production_day=production_day)
        if form.is_valid():
            message = form.cleaned_data['message']
            if message:
                url = reverse('workshop:production-day-reminder', kwargs={'production_day': pk, 'pk': form.cleaned_data['message'].pk})
            else:
                url = reverse('workshop:production-day-reminder', kwargs={'production_day': pk})
            return HttpResponseRedirect(url)
    return HttpResponseRedirect(reverse('workshop:'))
    

class ProductionDayReminderView(StaffPermissionsMixin, NextUrlMixin, UpdateView):
    form_class = ReminderMessageForm
    model = ReminderMessage
    template_name = 'workshop/productionday_reminder.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['select_message_form'] = self.get_select_message_form()
        context['production_day'] = self.production_day
        context['emails'] = {}
        for point_of_sale in PointOfSale.objects.all():
            context['emails'][point_of_sale.pk] = list(self.production_day.customer_orders.filter(point_of_sale=point_of_sale).values_list('customer__user__email', flat=True))
            
        context['emails']['all'] = list(self.production_day.customer_orders.all().values_list('customer__user__email', flat=True))
        context['messages_sent'] = ReminderMessage.objects.filter(production_day=self.production_day, state=ReminderMessage.State.SENT)
        return context
    
    def get_select_message_form(self):
        initial = {}
        if self.object:
            initial['message'] = self.object.pk
        return SelectReminderMessageForm(production_day=self.production_day, initial=initial)

    def get_object(self, queryset=None):
        self.production_day = ProductionDay.objects.get(pk=self.kwargs.get('production_day'))
        try:
            pk = self.kwargs.get(self.pk_url_kwarg)
            return ReminderMessage.objects.get(pk=pk, state=ReminderMessage.State.PLANNED)
        except ReminderMessage.DoesNotExist:
            return None
    
    # def get_form_kwargs(self) -> Dict[str, Any]:
    #     kwargs = super().get_form_kwargs()
    #     kwargs['production_day'] = self.production_day
    #     return kwargs

    def get_initial(self):
        initial = super().get_initial()
        email_settings = EmailSettings.load(request_or_site=self.request)
        if not self.object:
            initial.update({
                'subject': email_settings.get_subject_with_prefix(email_settings.production_day_reminder_subject),
                'body': email_settings.get_body_with_footer(email_settings.production_day_reminder_body),
            })
        initial['production_day'] = self.production_day
        return initial
    
    def post(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        return super().post(request, *args, **kwargs)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        if 'send' in self.request.POST:
            messages.add_message(self.request, messages.SUCCESS, 'Reminder message saved and send to selected orders.')
            self.object.send_messages()
        else:
            messages.add_message(self.request, messages.SUCCESS, 'Reminder message saved.')
        return HttpResponseRedirect(self.get_success_url())
    
    def get_success_url(self, *args, **kwargs):
        # if 'save' in self.request.POST:
        #     return reverse_lazy('workshop:production-day-detail', kwargs={'pk': self.production_day.pk})
        # else:
        return reverse_lazy('workshop:production-day-reminder', kwargs={'production_day': self.production_day.pk, 'pk': self.object.pk})
    


class ProductionDayReminderDeleteView(StaffPermissionsMixin, DeleteView):
    model = ReminderMessage

    def get_success_url(self, *args, **kwargs):
        return reverse_lazy('workshop:production-day-reminder', kwargs={'production_day': self.kwargs.get('production_day')})


class ProductionDayMetaProductView(StaffPermissionsMixin, NextUrlMixin, CreateView):
    model = CustomerOrder
    fields = ['customer',]
    template_name = "workshop/production_day_meta_product_form.html"
    production_day = None
    success_url = reverse_lazy('workshop:production-day-list')

    def dispatch(self, request, *args, **kwargs):
        self.production_day = ProductionDay.objects.get(pk=kwargs.get('pk'))
        self.object = self.production_day
        return super().dispatch(request, *args, **kwargs)

    def get_formset_initial(self):
        initial = []
        for meta_product in Product.objects.filter(category__name__iexact=settings.META_PRODUCT_CATEGORY_NAME):
            initial_meta_product = {
                'meta_product': meta_product.pk,
                'meta_product_name': meta_product,
                'product': None,
            }
            initial.append(initial_meta_product)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['production_day'] = self.production_day
        if self.request.POST:
            context['formset'] = ProductionDayMetaProductformSet(self.request.POST, initial=self.get_formset_initial(), form_kwargs={'production_day': self.production_day})
        else:
            context['formset'] = ProductionDayMetaProductformSet(initial=self.get_formset_initial(), form_kwargs={'production_day': self.production_day})
        context['product_mappings'] = ProductMapping.latest_product_mappings(3)
        return context

    def post(self, request, *args, **kwargs):
        formset = ProductionDayMetaProductformSet(request.POST, form_kwargs={'production_day': self.production_day})
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            raise Exception(formset.errors)
            return self.form_invalid(formset)

    def form_valid(self, formset):
        with transaction.atomic():
            meta_product_mapping = {}
            for form in formset:
                meta_product = Product.objects.get(pk=form.cleaned_data['meta_product'])
                product = form.cleaned_data['product']
                if product:
                    product_mapping, created = ProductMapping.objects.get_or_create(
                        source_product=meta_product,
                        target_product=product,
                        production_day=self.production_day
                    )
                    meta_product_mapping[meta_product] = {
                        'target_product': product,
                        'product_mapping': product_mapping,
                        'count': 0,
                    }
            for customer in Customer.objects.exclude(order_templates__isnull=True):
                if CustomerOrder.objects.filter(customer=customer, production_day=self.production_day).exists():
                    continue
                positions = CustomerOrderTemplatePosition.objects.active().filter(
                    order_template__customer=customer,
                    quantity__gt=0
                )
                for customer_order_template_position in positions:
                    if meta_product_mapping.get(customer_order_template_position.product, None):
                        customer_order, created = CustomerOrder.objects.get_or_create(
                            production_day=self.production_day,
                            customer=customer,
                            defaults={'point_of_sale': customer.point_of_sale}
                        )
                        position, created = CustomerOrderPosition.objects.get_or_create(
                            order=customer_order,
                            product=meta_product_mapping[customer_order_template_position.product]['target_product'],
                            defaults={
                                'quantity': customer_order_template_position.quantity
                            }
                        )
                        if not created:
                            position.quantity = position.quantity + customer_order_template_position.quantity
                            position.save(update_fields=['quantity'])
                        product_mapping = meta_product_mapping[customer_order_template_position.product]['product_mapping']
                        product_mapping.matched_count = (product_mapping.matched_count or 0) + 1
                        product_mapping.save(update_fields=['matched_count'])
                        
        return HttpResponseRedirect(self.get_success_url())
    

class CustomerListView(StaffPermissionsMixin, TableExportMixin, SingleTableMixin, FilterView):
    model = Customer
    table_class = CustomerTable
    filterset_class = CustomerFilter
    template_name = 'workshop/customer_list.html'

    @property
    def export_name(self):
        return "customers-{}".format(now().strftime("%Y%m%d-%H%M%S"))


class CustomerDeleteView(StaffPermissionsMixin, DeleteView):
    model = User
    template_name = 'workshop/customer_confirm_delete.html'

    def get_success_url(self):
        return reverse(
            'workshop:customer-list',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        context['deletable_objects'] = deletable_objects
        context['model_count'] = dict(model_count).items()
        context['protected'] = protected
        return context

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        try:
            self.object.delete()
        except ProtectedError as e:
            messages.error(request, e)
        finally:
            return redirect(success_url)

class CustomerDetailView(StaffPermissionsMixin, DetailView):
    model =  Customer
    template_name = "workshop/customer_detail.html"


class CustomerUpdateView(StaffPermissionsMixin, UpdateView):
    template_name = "workshop/customer_form.html"
    model =  Customer
    # fields = ['point_of_sale', 'user__first_name']
    form_class = CustomerForm
    success_url = reverse_lazy('workshop:customer-list')

    def get_initial(self):
        initial = super().get_initial()
        initial['first_name'] = self.object.user.first_name
        initial['last_name'] = self.object.user.last_name
        return initial
    
    def form_valid(self, form):
        self.object = form.save()
        self.object.user.first_name = form.cleaned_data['first_name']
        self.object.user.last_name = form.cleaned_data['last_name']
        self.object.user.save(update_fields=['first_name', 'last_name'])
        return HttpResponseRedirect(self.get_success_url())


class CustomerOrderListView(StaffPermissionsMixin, TableExportMixin, SingleTableMixin, FilterView):
    model = CustomerOrder
    table_class = CustomerOrderTable
    filterset_class = CustomerOrderFilter
    template_name = 'workshop/order_list.html'

    @property
    def export_name(self):
        return "orders-{}".format(now().strftime("%Y%m%d-%H%M%S"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_add_order'] = SelectProductionDayForm()
        return context
    

class CustomerReady2OrderExportView(StaffPermissionsMixin, ExportMixin, FilterView):
    filterset_class = CustomerOrderFilter
    model = Customer

    def get_headers(self):
        headers = ['kundennummer', 'kunde', 'kundengruppe', 'email', 'notizen', 'rechnung_vorname', 'rechnung_nachname', 'rechnung_straße', 'rechnung_plz', 'rechnung_stadt', 'rechnung_telefon']
        return headers

    def get_data(self):
        customers = self.object_list.order_by('pk')
        rows = []
        for customer in customers:
            rows.append([
                customer.id,
                customer.user.get_full_name(),
                'Kunden',
                customer.user.email,
                '',
                customer.user.first_name,
                customer.user.last_name,
                customer.address_line,
                customer.postal_code,
                customer.city,
                customer.telephone_number
            ])
        return rows

    @property
    def export_name(self):
        return "ready2order-{}".format(now().strftime("%d-%m-%Y"));


class ProductionDayExportView(StaffPermissionsMixin, ExportMixin, ListView):
    model = CustomerOrder
    template_name = 'workshop/order_list.html'


    def setup(self, request, *args, **kwargs):
        self.production_day = ProductionDay.objects.get(pk=kwargs.get('pk'))
        return super().setup(request, *args, **kwargs)
    
    def get_data(self):
        column_count = 5 + self.production_day.production_day_products.published().count()
        rows = []
        top_header = [''] * column_count
        top_header[0] = 'Produktionstag'
        top_header[1] = self.production_day.day_of_sale
        rows.append(top_header)
        rows.append([''] * column_count)
        headers = [
            'Nachname',
            'Vorname',
            'E-Mail',
            'Telefonnummer'
        ]
        production_day_products = self.production_day.production_day_products.published()
        for product in production_day_products:
            headers.append(product.product.get_short_name())
        headers.append('Abholstelle')
        rows.append(headers)
        for order in self.object_list.all():
            row = []
            row.extend([
                order.customer.user.last_name,
                order.customer.user.first_name,
                order.customer.user.email,
                order.customer.telephone_number
            ])
            for product in production_day_products:
                order_position = order.positions.filter(product=product.product).first()
                row.append(order_position and order_position.quantity or 0)
            pos = order.point_of_sale and order.point_of_sale.get_short_name() or ''
            row.append(pos)
            rows.append(row)
        # add footer

        rows.append([''] * column_count)
        footer = ['', '', '', '', ]
        footer2 = ['', '', '', '', ]
        for product in production_day_products:
            footer.append(product.get_order_quantity())
            footer2.append(product.max_quantity)
        footer.append('')
        footer2.append('')
        rows.append(footer)
        rows.append(footer2)
        return rows

    def get_headers(self):
        return []

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(production_day=self.production_day)

    @property
    def export_name(self):
        return "produktionstag-{}".format(self.production_day.day_of_sale.strftime("%d-%m-%Y"));


class CustomerOrderAddView(StaffPermissionsMixin, NextUrlMixin, CreateView):
    model = CustomerOrder
    fields = ['customer',]
    template_name = "workshop/batch_customerorder_form.html"
    production_day = None
    success_url = reverse_lazy('workshop:production-day-list')

    def dispatch(self, request, *args, **kwargs):
        if not 'pk' in kwargs and not request.POST.get('select_production_day', None):
            return HttpResponseRedirect(reverse('workshop:order-list'))
        if not 'pk' in kwargs:
            return HttpResponseRedirect(reverse('workshop:order-add', kwargs={'pk': request.POST.get('select_production_day')}))
        self.production_day = ProductionDay.objects.get(pk=kwargs.get('pk'))   
        self.object = ProductionDay.objects.get(pk=kwargs.get('pk'))  
        return super().dispatch(request, *args, **kwargs)

    def get_formset_initial(self):
        initial = []
        for customer in Customer.objects.all():
            initial_customer = {
                'customer': customer.pk,
                'customer_name': "{} ({})".format(customer, customer.user.email)
            }
            for product in self.production_day.production_day_products.all():
                quantity = None
                if CustomerOrderPosition.objects.filter(order__customer=customer, order__production_day=self.production_day, product=product.product).exists():
                    quantity = CustomerOrderPosition.objects.get(order__customer=customer, order__production_day=self.production_day, product=product.product).quantity
                initial_customer['product_{}'.format(product.product.pk)] = quantity
            initial.append(initial_customer)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['production_day'] = self.production_day
        if self.request.POST:
            context['formset'] = BatchCustomerOrderFormSet(self.request.POST, initial=self.get_formset_initial(), form_kwargs={'production_day': self.production_day})
        else:
            context['formset'] = BatchCustomerOrderFormSet(initial=self.get_formset_initial(), form_kwargs={'production_day': self.production_day})
        return context

    def post(self, request, *args, **kwargs):
        formset = BatchCustomerOrderFormSet(request.POST, form_kwargs={'production_day': self.production_day})
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        with transaction.atomic():
            for form in formset:
                customer = form.cleaned_data['customer']
                customer = Customer.objects.get(pk=customer)
                products = {k:v for k, v in form.cleaned_data.items() if k.startswith('product_')}
                # if customer.pk == 2:
                #     raise Exception(not any([v and v > 0 for v in products.values()]))
                if not any([v and v > 0 for v in products.values()]):
                    CustomerOrder.objects.filter(production_day=self.production_day, customer=customer).delete()
                    continue
                customer_order, created = CustomerOrder.objects.get_or_create(
                    production_day=self.production_day,
                    customer=customer,
                    defaults={'point_of_sale': customer.point_of_sale}
                )
                for product in Product.objects.filter(production_days__production_day=self.production_day):
                    quantity = form.cleaned_data['product_%s' % (product.pk,)]
                    if not quantity or quantity == 0:
                        CustomerOrderPosition.objects.filter(order=customer_order, product=product).delete()
                    else:
                        position, created = CustomerOrderPosition.objects.update_or_create(
                            order=customer_order,
                            product=product,
                            defaults={
                                'quantity': quantity
                            }
                        )
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, formset):
        for form_error in formset.errors:
            if form_error:
                messages.error(self.request, form_error)
        if formset.non_form_errors():
            messages.error(self.request, formset.non_form_errors())
        return self.render_to_response(self.get_context_data())


class CustomerOrderDeleteView(DeleteView):
    model = CustomerOrder
    template_name = 'workshop/customerorder_confirm_delete.html'

    def get_success_url(self):
        return reverse(
            'workshop:order-list',
        )

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        try:
            self.object.delete()
        except ProtectedError as e:
            messages.error(request, e)
        finally:
            return redirect(success_url)


class CreateUpdateInstructionsView(UpdateView):
    model = Instruction
    fields = ['instruction']

    def get_object(self, queryset=None):
        obj, created = Instruction.objects.get_or_create(
            product__pk=self.kwargs['pk']
            , defaults={'product': Product.objects.get(pk=self.kwargs['pk'])})
        return obj

    def get_success_url(self):
        return reverse('workshop:product-detail', kwargs={'pk': self.kwargs['pk']})


class BatchCustomerTemplateView(StaffPermissionsMixin, CreateView):
    model = CustomerOrderTemplate
    fields = ['customer',]
    template_name = "workshop/batch_customerordertemplate_form.html"

    def get_formset_initial(self):
        initial = []
        for customer in Customer.objects.all():
            initial_customer = {
                'customer': str(customer.pk),
                'customer_name': "{} ({})".format(customer, customer.user.email)
            }
            for product in Product.objects.filter(is_recurring=True):
                quantity = None
                if CustomerOrderTemplatePosition.objects.active().filter(order_template__customer=customer, product=product).exists():
                    quantity = CustomerOrderTemplatePosition.objects.active().get(order_template__customer=customer, product=product).quantity
                initial_customer['product_{}'.format(product.pk)] = quantity
            initial.append(initial_customer)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = BatchCustomerOrderTemplateFormSet(self.request.POST, initial=self.get_formset_initial())
        else:
            context['formset'] = BatchCustomerOrderTemplateFormSet(initial=self.get_formset_initial())
        return context

    def post(self, request, *args, **kwargs):
        formset = BatchCustomerOrderTemplateFormSet(request.POST, initial=self.get_formset_initial())
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        with transaction.atomic():
            for form in formset:
                if form.has_changed():
                    customer = form.cleaned_data['customer']
                    customer = Customer.objects.get(pk=customer)
                    # raise Exception(form.changed_data, self.request.POST, self.get_formset_initial())
                    products_recurring = {Product.objects.get(pk=k.replace('product_', '')): int(form.cleaned_data.get('product_{}'.format(k.replace('product_', '')))) for k, v in form.cleaned_data.items() if k.startswith('product_') and v}
                    order_template = CustomerOrderTemplate.create_customer_order_template(
                        self.request,
                        customer,
                        products_recurring,
                    )
        return HttpResponseRedirect(reverse('workshop:customer-list'))

    def form_invalid(self, formset):
        return self.render_to_response(self.get_context_data())
    

class PointOfSaleCreateView(StaffPermissionsMixin, CreateView):
    model = PointOfSale
    fields = ('name', 'short_name', 'is_primary')
    template_name = 'workshop/point_of_sale_form.html'

    def get_success_url(self):
        return reverse('workshop:point-of-sale-list')


class PointOfSaleListView(StaffPermissionsMixin, SingleTableView):
    model = PointOfSale
    table_class = PointOfSaleTable
    template_name = 'workshop/point_of_sale_list.html'


class PointOfSaleUpdateView(StaffPermissionsMixin, UpdateView):
    model = PointOfSale
    fields = ('name', 'short_name', 'is_primary')
    template_name = 'workshop/point_of_sale_form.html'

    def get_success_url(self):
        return reverse('workshop:point-of-sale-list')


class PointOfSaleDeleteView(StaffPermissionsMixin, DeleteView):
    model = PointOfSale
    template_name = 'workshop/point_of_sale_confirm_delete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        context['deletable_objects'] = deletable_objects
        context['model_count'] = dict(model_count).items()
        context['protected'] = protected
        return context

    def get_success_url(self):
        return reverse('workshop:point-of-sale-list')