from itertools import product
from typing import OrderedDict

from django.db import IntegrityError, transaction
from django.contrib import messages
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, DeleteView, UpdateView, TemplateView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.db.models import Sum
from django.utils.timezone import make_aware

from django_tables2 import SingleTableView

from bakeup.core.views import StaffPermissionsMixin
from bakeup.shop.forms import ProductionDayProductFormSet, ProductionDayForm
from bakeup.shop.models import CustomerOrder, CustomerOrderPosition, ProductionDay, ProductionDayProduct
from bakeup.workshop.forms import ProductForm, ProductHierarchyForm, ProductionPlanDayForm, ProductionPlanForm, SelectProductForm
from bakeup.workshop.models import Category, Product, ProductHierarchy, ProductionPlan
from bakeup.workshop.tables import ProductTable, ProductionDayTable, ProductionPlanTable



class WorkshopView(StaffPermissionsMixin, TemplateView):
    template_name = 'workshop/workshop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products_count'] = Product.objects.filter(is_sellable=True).count()
        context['ingredients_count'] = Product.objects.all().count()
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


    def get_context_data(self, **kwargs):
        # raise Exception(self.object.parents.all())
        return super().get_context_data(**kwargs)


class IngredientListView(StaffPermissionsMixin, SingleTableView):
    model = Product
    table_class = ProductTable


class ProductListView(StaffPermissionsMixin, SingleTableView):
    model = Product
    table_class = ProductTable

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(is_sellable=True)
        return qs


class IngredientListView(StaffPermissionsMixin, SingleTableView):
    model = Product
    table_class = ProductTable


class ProductionPlanListView(StaffPermissionsMixin, SingleTableView):
    model = ProductionPlan
    context_object_name = 'production_plans'

    def get_queryset(self):
        qs = super().get_queryset()
        if 'production_day' in self.request.GET:
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
        if 'production_day' in self.request.GET:
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
                context['formset'].can_delete = True
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