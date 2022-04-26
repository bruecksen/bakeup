from itertools import product
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, DeleteView, UpdateView, TemplateView, FormView
from django.views.generic.detail import SingleObjectMixin
from django.db.models import Sum

from django_tables2 import SingleTableView

from bakeup.core.views import StaffPermissionsMixin
from bakeup.shop.models import CustomerOrder, CustomerOrderPosition
from bakeup.workshop.forms import ProductForm, ProductHierarchyForm, ProductionPlanForm, SelectProductForm
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
    table_class = ProductionPlanTable


class ProductionPlanDetailView(StaffPermissionsMixin, DetailView):
    model = ProductionPlan


class ProductionPlanAddView(StaffPermissionsMixin, FormView):
    model = ProductionPlan
    form_class = ProductionPlanForm
    template_name = 'workshop/production_plan_form.html'

    def form_valid(self, form):
        production_day = form.cleaned_data['production_day']
        if production_day:
            positions = CustomerOrderPosition.objects.filter(order__production_day=production_day)
            product_quantities = positions.values('product').order_by('product').annotate(total_quantity=Sum('quantity'))
            for product_quantity in product_quantities:
                obj, created = ProductionPlan.objects.update_or_create(
                    parent_plan=None,
                    product_id=product_quantity.get('product'),
                    defaults={'quantity': product_quantity.get('total_quantity')}
                )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('workshop:production-plan-list')


class CategoryListView(StaffPermissionsMixin, ListView):
    model = Category


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.get_root_nodes()
        return context