from itertools import product
from typing import OrderedDict

from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import resolve, reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, DeleteView, UpdateView, TemplateView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.db.models import Sum
from django.utils.timezone import make_aware

from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView

from bakeup.workshop.templatetags.workshop_tags import clever_rounding 
from bakeup.core.views import StaffPermissionsMixin
from bakeup.shop.forms import ProductionDayProductFormSet, ProductionDayForm
from bakeup.shop.models import CustomerOrder, CustomerOrderPosition, ProductionDay, ProductionDayProduct
from bakeup.workshop.forms import AddProductForm, AddProductFormSet, ProductForm, ProductHierarchyForm, ProductKeyFiguresForm, ProductionPlanDayForm, ProductionPlanForm, SelectProductForm
from bakeup.workshop.models import Category, Product, ProductHierarchy, ProductionPlan
from bakeup.workshop.tables import CustomerOrderFilter, CustomerOrderTable, ProductFilter, ProductTable, ProductionDayTable, ProductionPlanTable



class WorkshopView(StaffPermissionsMixin, TemplateView):
    template_name = 'workshop/workshop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recipies_count'] = Product.objects.filter(is_sellable=True).count()
        context['products_count'] = Product.objects.all().count()
        context['categories_count'] = Category.objects.all().count()
        context['productionplans_count'] = ProductionPlan.objects.all().count()
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
        self.object = product
        if self.product_parent:
            self.product_parent.add_child(product)
        return HttpResponseRedirect(self.get_success_url())

@staff_member_required
def product_add_inline_view(request, pk):
    parent_product = Product.objects.get(pk=pk)
    if request.method == 'POST':
        formset = AddProductFormSet(request.POST)
        if formset.is_valid():
            for form in formset:
                if form.cleaned_data.get('product_existing', None) and form.cleaned_data.get('weight', None):
                    product = form.cleaned_data['product_existing']
                    if parent_product.has_child(product):
                        product = None
                        messages.add_message(request, messages.WARNING, "This product is already a child product.")
                    if parent_product == product:
                        product = None
                        messages.add_message(request, messages.WARNING, "You cannot add the parent product as a child product again")
                if form.cleaned_data.get('product_new', None) and form.cleaned_data.get('weight', None) and form.cleaned_data.get('category', None):
                    product = Product.objects.create(
                        name=form.cleaned_data['product_new'],
                        category=form.cleaned_data['category'],
                        weight=1000,
                        is_sellable=form.cleaned_data.get('is_sellable', False),
                        is_buyable=form.cleaned_data.get('is_buyable', False),
                        is_composable=form.cleaned_data.get('is_composable', False),
                    )
                if product:
                    quantity =  form.cleaned_data['weight'] / product.weight
                    parent_product.add_child(product, quantity)
    return HttpResponseRedirect(reverse('workshop:product-detail', kwargs={'pk': parent_product.pk}))

class ProductUpdateView(StaffPermissionsMixin, UpdateView):
    model = Product
    form_class = ProductForm


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
        context['formset'] = AddProductFormSet(form_kwargs={'parent_products': self.object.childs.all(), 'product': self.object})
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


class ProductionPlanListView(StaffPermissionsMixin, SingleTableView):
    model = ProductionPlan
    context_object_name = 'production_plans'

    def get_queryset(self):
        qs = super().get_queryset()
        if 'production_day' in self.request.GET and self.request.GET.get('production_day').isnumeric():
            qs = qs.filter(production_day__pk=self.request.GET.get('production_day'))
        return qs.filter(parent_plan__isnull=True)

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table_header = ProductionPlan.objects.filter(parent_plan__isnull=False).values_list('product__category__name', flat=True).order_by('product__category__name').distinct()
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
        # raise Exception(production_plans)
        context['table_categories'] = table_categories
        context['days'] = ProductionPlan.objects.all().values_list('production_day__day_of_sale', 'production_day__pk').order_by('production_day__day_of_sale').distinct()
        context['production_plans'] = production_plans
        if 'production_day' in self.request.GET and self.request.GET.get('production_day').isnumeric():
            context['day_filter'] = ProductionDay.objects.get(pk=self.request.GET.get('production_day', None))
        return context


class ProductionPlanDetailView(StaffPermissionsMixin, DetailView):
    model = ProductionPlan


class ProductionPlanAddView(StaffPermissionsMixin, FormView):
    model = ProductionPlan
    form_class = ProductionPlanDayForm
    template_name = 'workshop/production_plan_form.html'

    def form_valid(self, form):
        production_day = form.cleaned_data['production_day']
        if production_day:
            positions = CustomerOrderPosition.objects.filter(order__production_day=production_day, production_plan__isnull=True)
            product_quantities = positions.values('product').order_by('product').annotate(total_quantity=Sum('quantity'))
            for product_quantity in product_quantities:
                if product_quantity.get('total_quantity') == 0:
                    continue
                product = Product.duplicate(Product.objects.get(pk=product_quantity.get('product')))
                obj = ProductionPlan.objects.create(
                    parent_plan=None,
                    production_day=production_day,
                    product=product,
                    quantity=product_quantity.get('total_quantity'),
                    start_date=production_day.day_of_sale,
                )
                ProductionPlan.create_all_child_plans(obj, obj.product.parents.all(), quantity_parent=product_quantity.get('total_quantity'))
                positions.filter(product_id=product_quantity.get('product')).update(production_plan=obj)
                production_day_product = ProductionDayProduct.objects.get(product_id=product_quantity.get('product'), production_day=production_day)
                production_day_product.production_plan = obj
                production_day_product.product = product
                production_day_product.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('workshop:production-plan-list')


class ProductionPlanUpdateView(StaffPermissionsMixin, UpdateView):
    model = ProductionPlan
    form_class = ProductionPlanForm


    def get_success_url(self):
        if self.object.parent_plan:
            return reverse('workshop:production-plan-detail', kwargs={'pk': self.object.parent_plan.pk })
        else:
            return reverse('workshop:production-plan-detail', kwargs={'pk': self.object.pk })


class ProductionPlanDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductionPlan


    def get_success_url(self):
        return reverse('workshop:production-plan-list')


class CategoryListView(StaffPermissionsMixin, ListView):
    model = Category


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.get_root_nodes()
        return context




class ProductionDayListView(StaffPermissionsMixin, SingleTableView):
    model = ProductionDay
    table_class = ProductionDayTable
    template_name = "workshop/productionday_list.html"


class ProductionDayMixin(object):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = ProductionDayProductFormSet(self.request.POST)
            context['form'] = ProductionDayForm(data=self.request.POST)
        else:
            context['formset'] = ProductionDayProductFormSet(queryset=ProductionDayProduct.objects.filter(production_day=self.object))
            if self.object:
                context['formset'].extra = 0
            context['form'] = ProductionDayForm(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        formset = ProductionDayProductFormSet(request.POST, queryset=ProductionDayProduct.objects.filter(production_day=self.object))
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
                obj.delete()
            for instance in instances:
                instance.production_day = production_day
                instance.save()
        return HttpResponseRedirect(reverse('workshop:production-day-list'))

    def form_invalid(self, form, formset):
        return self.render_to_response(self.get_context_data())


class ProductionDayAddView(ProductionDayMixin, CreateView):
    template_name = "workshop/productionday_form.html"
    model =  ProductionDay
    form_class = ProductionDayForm

    def get_object(self, queryset=None):
        return None


class ProductionDayUpdateView(ProductionDayMixin, UpdateView):
    template_name = "workshop/productionday_form.html"
    model =  ProductionDay
    form_class = ProductionDayForm

    def get_object(self):
        object = super().get_object()
        if object.is_locked:
            raise Http404()
        return object


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
            'workshop:production-day-list',
        )


class CustomerOrderListView(StaffPermissionsMixin, SingleTableMixin, FilterView):
    model = CustomerOrder
    table_class = CustomerOrderTable
    filterset_class = CustomerOrderFilter
    template_name = 'workshop/order_list.html'