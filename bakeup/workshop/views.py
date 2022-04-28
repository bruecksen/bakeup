from itertools import product
from typing import OrderedDict
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, DeleteView, UpdateView, TemplateView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.db.models import Sum

from django_tables2 import SingleTableView

from bakeup.core.views import StaffPermissionsMixin
from bakeup.shop.models import CustomerOrder, CustomerOrderPosition, ProductionDayProduct
from bakeup.workshop.forms import ProductForm, ProductHierarchyForm, ProductionDayForm, ProductionPlanForm, SelectProductForm
from bakeup.workshop.models import Category, Product, ProductHierarchy, ProductionPlan
from bakeup.workshop.tables import ProductTable, ProductionPlanTable



class WorkshopView(StaffPermissionsMixin, TemplateView):
    template_name = 'workshop/workshop.html'


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


class ProductListView(StaffPermissionsMixin, SingleTableView):
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
        for category in ProductionPlan.objects.filter(parent_plan__isnull=False).values_list('product__category__name', flat=True):
            if not category in table_categories:
                table_categories[category] = {
                }
        production_plans = []
        for production_plan in context['production_plans']:
            plan_dict = {
                'root': production_plan
            }
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
        context['day_filter'] = self.request.GET.get('production_day', None)
        return context


class ProductionPlanDetailView(StaffPermissionsMixin, DetailView):
    model = ProductionPlan


class ProductionPlanAddView(StaffPermissionsMixin, FormView):
    model = ProductionPlan
    form_class = ProductionDayForm
    template_name = 'workshop/production_plan_form.html'

    def form_valid(self, form):
        production_day = form.cleaned_data['production_day']
        if production_day:
            positions = CustomerOrderPosition.objects.filter(order__production_day=production_day, production_plan__isnull=True)
            product_quantities = positions.values('product').order_by('product').annotate(total_quantity=Sum('quantity'))
            for product_quantity in product_quantities:
                obj = ProductionPlan.objects.create(
                    parent_plan=None,
                    production_day=production_day,
                    product_id=product_quantity.get('product'),
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