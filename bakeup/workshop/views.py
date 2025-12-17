from typing import Any, OrderedDict

from dal.views import BaseQuerySetView
from dal_select2.views import Select2ViewMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Group
from django.db import connection, transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.datastructures import MultiValueDict
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_filters.views import FilterView
from django_htmx.http import HttpResponseClientRefresh
from django_tables2 import SingleTableMixin, SingleTableView
from django_tables2.export import ExportMixin as TableExportMixin
from taggit.models import Tag
from treebeard.forms import movenodeform_factory

from bakeup.contrib.forms import NoteForm
from bakeup.contrib.models import Note
from bakeup.core.utils import get_deleted_objects
from bakeup.core.views import NextUrlMixin, StaffPermissionsMixin
from bakeup.pages.models import EmailSettings
from bakeup.shop.forms import (
    BatchCustomerOrderFormSet,
    BatchCustomerOrderTemplateFormSet,
    CustomerOrderPositionFormSet,
    ProductionDayForm,
    ProductionDayProductFormSet,
)
from bakeup.shop.models import (
    Customer,
    CustomerOrder,
    CustomerOrderPosition,
    CustomerOrderTemplate,
    CustomerOrderTemplatePosition,
    PointOfSale,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.users.models import User
from bakeup.workshop.forms import (
    AddProductFormSet,
    CustomerForm,
    CustomerOrderForm,
    ProductForm,
    ProductHierarchyForm,
    ProductionDayMetaProductformSet,
    ProductionPlanDayForm,
    ProductKeyFiguresForm,
    ReminderMessageForm,
    SelectProductForm,
    SelectProductionDayForm,
    SelectReminderMessageForm,
)
from bakeup.workshop.models import (
    Category,
    Instruction,
    Product,
    ProductHierarchy,
    ProductionPlan,
    ProductMapping,
    ProductPrice,
    ReminderMessage,
)
from bakeup.workshop.tables import (
    CustomerFilter,
    CustomerOrderFilter,
    CustomerOrderTable,
    CustomerOrderTemplateTable,
    CustomerTable,
    GroupTable,
    PointOfSaleTable,
    ProductFilter,
    ProductionDayTable,
    ProductionPlanFilter,
    ProductTable,
)
from bakeup.workshop.templatetags.workshop_tags import clever_rounding


class WorkshopView(StaffPermissionsMixin, TemplateView):
    template_name = "workshop/workshop.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recipies_count"] = Product.objects.filter(is_sellable=True).count()
        context["products_count"] = Product.objects.all().count()
        context["categories_count"] = Category.objects.all().count()
        context["productionplans_count"] = ProductionPlan.objects.all().count()
        context["productiondays_count"] = ProductionDay.objects.all().count()
        context["customers_count"] = Customer.objects.all().count()
        context["orders_count"] = CustomerOrder.objects.all().count()
        context["recurring_orders_count"] = (
            CustomerOrderTemplate.objects.active().count()
        )
        upcoming_production_days = ProductionDay.objects.upcoming()
        context["upcoming_production_days"] = upcoming_production_days[:5]
        context["upcoming_production_days_count"] = upcoming_production_days.count()
        context["past_production_days"] = ProductionDay.objects.past()[:5]
        context["past_production_days_count"] = ProductionDay.objects.past().count()
        context["production_plans"] = ProductionPlan.objects.filter(
            production_day=upcoming_production_days.first(), parent_plan__isnull=True
        )
        context["points_of_sale"] = PointOfSale.objects.all()
        return context


class ProductAddView(StaffPermissionsMixin, CreateView):
    model = Product
    form_class = ProductForm
    form_select_class = SelectProductForm
    product_parent = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_select"] = SelectProductForm()
        context["product_parent"] = self.product_parent
        return context

    def dispatch(self, request, *args, **kwargs):
        if "pk" in kwargs:
            self.product_parent = get_object_or_404(Product, pk=self.kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if "add-existing" in request.POST:
            form = SelectProductForm(request.POST)
            if form.is_valid():
                product = form.cleaned_data["product"]
                self.object = self.product_parent
                self.product_parent.add_child(product)
            return HttpResponseRedirect(self.get_success_url())
        elif "add-new" in request.POST:
            return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        product = form.save()
        price = form.cleaned_data["price"]
        if price:
            price, created = ProductPrice.objects.update_or_create(
                product=product,
                defaults={"price": price},
            )
        self.object = product
        if self.product_parent:
            self.product_parent.add_child(product)
        return HttpResponseRedirect(self.get_success_url())


@staff_member_required(login_url="login")
def product_add_inline_view(request, pk):
    parent_product = Product.objects.get(pk=pk)
    if request.method == "POST":
        formset = AddProductFormSet(request.POST)
        if formset.is_valid():
            for form in formset:
                product = None
                quantity = None
                if form.cleaned_data.get(
                    "product_existing", None
                ) and form.cleaned_data.get("weight", None):
                    product = form.cleaned_data["product_existing"]
                    if parent_product.has_child(product):
                        product = None
                        messages.add_message(
                            request,
                            messages.WARNING,
                            "This product is already a child product.",
                        )
                    if parent_product == product:
                        product = None
                        messages.add_message(
                            request,
                            messages.WARNING,
                            "You cannot add the parent product as a child product"
                            " again",
                        )
                    quantity = (
                        form.cleaned_data.get("weight", 1000)
                        / product.weight_in_base_unit
                    )
                if form.cleaned_data.get("product_new", None) and form.cleaned_data.get(
                    "category", None
                ):
                    product = Product.objects.create(
                        name=form.cleaned_data["product_new"],
                        category=form.cleaned_data["category"],
                        weight=1000,
                        is_sellable=form.cleaned_data.get("is_sellable", False),
                        is_buyable=form.cleaned_data.get("is_buyable", False),
                        is_composable=form.cleaned_data.get("is_composable", False),
                    )
                    quantity = (
                        form.cleaned_data.get("weight", 1000)
                        / product.weight_in_base_unit
                    )
                elif form.cleaned_data.get(
                    "product_new", None
                ) and not form.cleaned_data.get("category", None):
                    messages.add_message(
                        request,
                        messages.WARNING,
                        "Bitte eine Kategorie für das neue Produkt auswählen.",
                    )
                if product and quantity:
                    parent_product.add_child(product, quantity)
        else:
            raise Exception(formset.errors)
    return HttpResponseRedirect(
        reverse("workshop:product-detail", kwargs={"pk": parent_product.pk})
    )


class ProductUpdateView(StaffPermissionsMixin, UpdateView):
    model = Product
    form_class = ProductForm

    def form_valid(self, form):
        product = form.save()
        price = form.cleaned_data["price"]
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
            "workshop:product-list",
        )


class ProductHierarchyDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductHierarchy

    def get_success_url(self):
        return reverse("workshop:product-detail", kwargs={"pk": self.object.parent.pk})


class ProductHierarchyUpdateView(StaffPermissionsMixin, FormView):
    model = ProductHierarchy
    form_class = ProductHierarchyForm

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(ProductHierarchy, pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        amount = form.cleaned_data["amount"]
        if amount and self.object.child.weight_in_base_unit:
            self.object.quantity = amount / self.object.child.weight_in_base_unit
            self.object.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        raise Exception(form.errors)
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("workshop:product-detail", kwargs={"pk": self.object.parent.pk})


class ProductDetailView(StaffPermissionsMixin, DetailView):
    model = Product

    def get_key_figures_inital_data(self):
        return {
            "fermentation_loss": clever_rounding(self.object.get_fermentation_loss()),
            "dough_yield": self.object.get_dough_yield(),
            "salt": clever_rounding(self.object.get_salt_ratio()),
            "starter": self.object.get_starter_ratio(),
            "wheat": self.object.get_wheats(),
            "pre_ferment": clever_rounding(self.object.get_pre_ferment_ratio()),
            "total_dough_weight": clever_rounding(self.object.total_weight),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["formset"] = AddProductFormSet(
            form_kwargs={
                "parent_products": self.object.childs.with_weights(),
                "product": self.object,
            }
        )
        if self.object.is_composable:
            context["key_figures_form"] = ProductKeyFiguresForm(
                initial=self.get_key_figures_inital_data()
            )
        return context


def product_normalize_view(request, pk):
    product = Product.objects.get(pk=pk)
    if request.method == "POST":
        form = ProductKeyFiguresForm(request.POST)
        if form.is_valid():
            fermentation_loss = form.cleaned_data["fermentation_loss"]
            product.normalize(fermentation_loss)
        else:
            raise Exception(form.errors)
    return redirect(product.get_absolute_url())


class RecipeDetailView(StaffPermissionsMixin, DetailView):
    model = Product
    template_name = "workshop/recipe_detail.html"

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
    template_name = "workshop/product_list.html"

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(is_sellable=True)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_name"] = _("Recipe")
        context["object_name_plural"] = _("Recipes")
        return context


class ProductListView(StaffPermissionsMixin, SingleTableMixin, FilterView):
    model = Product
    table_class = ProductTable
    filterset_class = ProductFilter
    template_name = "workshop/product_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_name"] = _("Product")
        context["object_name_plural"] = _("Products")
        return context


@staff_member_required(login_url="login")
def production_plan_redirect_view(request):
    if request.method == "POST":
        form = ProductionPlanDayForm(request.POST)
        if form.is_valid():
            url = reverse(
                "workshop:production-plan-production-day",
                kwargs={"pk": form.cleaned_data["production_day"].pk},
            )
            return HttpResponseRedirect(url)
    production_day = ProductionDay.objects.upcoming().first()
    if not production_day:
        production_day = ProductionDay.objects.all().first()
    if production_day:
        url = reverse(
            "workshop:production-plan-production-day",
            kwargs={"pk": production_day.pk},
        )
    else:
        url = reverse("workshop:production-plan-list")
    return HttpResponseRedirect(url)


class ProductionPlanOfProductionDay(StaffPermissionsMixin, ListView):
    model = ProductionPlan
    context_object_name = "production_plans"
    template_name = "workshop/productionplan_productionday.html"
    ordering = ("-production_day", "product__name")
    production_day = None

    def setup(self, request, *args, **kwargs):
        self.production_day = ProductionDay.objects.get(pk=kwargs["pk"])
        return super().setup(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(parent_plan__isnull=True, production_day=self.production_day)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table_categories = OrderedDict()
        for category in (
            ProductionPlan.objects.filter(parent_plan__isnull=False)
            .order_by("pk")
            .values_list("product__category__name", flat=True)
        ):
            if category not in table_categories:
                table_categories[category] = {}
        production_plans = []
        for production_plan in context["production_plans"]:
            plan_dict = OrderedDict()
            plan_dict["root"] = production_plan
            for child in ProductionPlan.objects.filter(
                Q(parent_plan=production_plan)
                | Q(parent_plan__parent_plan=production_plan)
                | Q(parent_plan__parent_plan__parent_plan=production_plan)
                | Q(parent_plan__parent_plan__parent_plan__parent_plan=production_plan)
            ):
                plan_dict.setdefault(child.product.category.name, [])
                plan_dict[child.product.category.name].append(child)
            production_plans.append(plan_dict)
        context["table_categories"] = table_categories
        context["production_plans"] = production_plans
        context["production_day"] = self.production_day
        context["production_day_form"] = ProductionPlanDayForm(
            initial={"production_day": self.production_day}
        )
        try:
            context["production_day_prev"] = ProductionDay.get_previous_by_day_of_sale(
                self.production_day
            )
        except ProductionDay.DoesNotExist:
            pass
        try:
            context["production_day_next"] = ProductionDay.get_next_by_day_of_sale(
                self.production_day
            )
        except ProductionDay.DoesNotExist:
            pass
        context["has_plans_to_start"] = (
            self.get_queryset().filter(state=ProductionPlan.State.PLANNED).exists()
        )
        context["has_plans_to_finish"] = (
            self.get_queryset()
            .filter(state=ProductionPlan.State.IN_PRODUCTION)
            .exists()
        )
        return context


class ProductionPlanListView(StaffPermissionsMixin, FilterView):
    model = ProductionPlan
    context_object_name = "production_plans"
    filterset_class = ProductionPlanFilter
    template_name = "workshop/productionplan_list.html"
    ordering = ("-production_day", "product__name")

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(parent_plan__isnull=True)

    def get_filterset_kwargs(self, filterset_class):
        kwargs = super().get_filterset_kwargs(filterset_class)
        if kwargs["data"] is None:
            filter_values = MultiValueDict()
        else:
            filter_values = kwargs["data"].copy()

        if not filter_values:
            # we need to use `setlist` for multi-valued fields to emulate this coming from a query dict
            filter_values.setlist("state", ["0", "1"])

        kwargs["data"] = filter_values
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table_categories = OrderedDict()
        for category in (
            ProductionPlan.objects.filter(parent_plan__isnull=False)
            .order_by("pk")
            .values_list("product__category__name", flat=True)
        ):
            if category not in table_categories:
                table_categories[category] = {}
        production_plans = []
        for production_plan in context["production_plans"]:
            plan_dict = OrderedDict()
            plan_dict["root"] = production_plan
            for child in ProductionPlan.objects.filter(
                Q(parent_plan=production_plan)
                | Q(parent_plan__parent_plan=production_plan)
                | Q(parent_plan__parent_plan__parent_plan=production_plan)
                | Q(parent_plan__parent_plan__parent_plan__parent_plan=production_plan)
            ):
                plan_dict.setdefault(child.product.category.name, [])
                plan_dict[child.product.category.name].append(child)
            production_plans.append(plan_dict)
        context["table_categories"] = table_categories
        context["production_plans"] = production_plans
        context["day_of_sale_selected"] = (
            context["filter"].form.cleaned_data.get("production_day") or ""
        )
        return context


class ProductionPlanDetailView(StaffPermissionsMixin, DetailView):
    model = ProductionPlan


class ProductionPlanAddView(StaffPermissionsMixin, FormView):
    model = ProductionPlan
    form_class = ProductionPlanDayForm
    template_name = "workshop/production_plan_form.html"

    def form_valid(self, form):
        production_day = form.cleaned_data["production_day"]
        self.production_day = production_day
        if production_day:
            production_day.create_or_update_production_plans(
                state=ProductionPlan.State.PLANNED, create_max_quantity=True
            )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "workshop:production-plan-production-day",
            kwargs={"pk": self.production_day.pk},
        )


@staff_member_required(login_url="login")
def production_plan_update(
    request,
    pk,
):
    production_plan = ProductionPlan.objects.get(pk=pk)
    if production_plan.is_planned or production_plan.is_canceled:
        product = production_plan.product.product_template
        production_day = production_plan.production_day
        production_day_product = ProductionDayProduct.objects.get(
            production_day=production_day, product=product
        )
        production_day.update_production_plan(
            product=product,
            quantity=production_day_product.max_quantity,
            state=ProductionPlan.State.PLANNED,
            create_max_quantity=True,
        )
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(
        reverse(
            "workshop:production-plan-production-day", kwargs={"pk": production_day.pk}
        )
    )


@staff_member_required(login_url="login")
def production_plans_start_view(request, production_day):
    production_day = ProductionDay.objects.get(pk=production_day)
    production_plans = ProductionPlan.objects.filter(
        production_day=production_day,
        state=ProductionPlan.State.PLANNED,
        parent_plan__isnull=True,
    )
    production_plans_updated = []
    for production_plan in production_plans:
        production_day_product = ProductionDayProduct.objects.filter(
            product=production_plan.product.product_template,
            production_day=production_day,
        )
        if not production_day_product.exists():
            production_plan.delete()
            continue
        production_plans_updated.append(
            production_plan.production_day.create_or_update_production_plan(
                product=production_plan.product.product_template,
                state=ProductionPlan.State.IN_PRODUCTION,
                create_max_quantity=False,
            )
        )
    # raise Exception(production_plans)
    for production_plan in production_plans_updated:
        production_plan.production_day.update_order_positions_product(
            production_plan.product
        )
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(reverse("workshop:production-plan-next"))


@staff_member_required(login_url="login")
def production_plan_start_view(request, pk):
    production_plan = ProductionPlan.objects.get(pk=pk)
    if production_plan.get_next_state() == ProductionPlan.State.IN_PRODUCTION:
        production_plan = (
            production_plan.production_day.create_or_update_production_plan(
                product=production_plan.product.product_template,
                state=ProductionPlan.State.IN_PRODUCTION,
                create_max_quantity=False,
            )
        )
        production_plan.production_day.update_order_positions_product(
            production_plan.product
        )
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(
        reverse(
            "workshop:production-plan-production-day",
            kwargs={"pk": production_plan.production_day.pk},
        )
    )


@staff_member_required(login_url="login")
def production_plans_finish_view(request, production_day):
    production_day = ProductionDay.objects.get(pk=production_day)
    production_plans = ProductionPlan.objects.filter(
        production_day=production_day,
        state=ProductionPlan.State.IN_PRODUCTION,
        parent_plan__isnull=True,
    )
    production_plans.update(state=ProductionPlan.State.PRODUCED)
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(reverse("workshop:production-plan-next"))


@staff_member_required(login_url="login")
def production_plan_finish_view(request, pk):
    production_plan = ProductionPlan.objects.get(pk=pk)
    if production_plan.is_production:
        production_plan.set_state(ProductionPlan.State.PRODUCED)
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(reverse("workshop:production-plan-next"))


@staff_member_required(login_url="login")
def production_plan_cancel_view(request, pk):
    production_plan = ProductionPlan.objects.get(pk=pk)
    production_plan.set_state(ProductionPlan.State.CANCELED)
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(
        reverse(
            "workshop:production-plan-production-day",
            kwargs={"pk": production_plan.production_day.pk},
        )
    )


@require_POST
@staff_member_required(login_url="login")
def customer_order_toggle_picked_up_view(request, pk):
    customer_order = CustomerOrder.objects.get(pk=pk)
    customer_order.positions.all().update(is_picked_up=not customer_order.is_picked_up)
    return HttpResponse()


@staff_member_required(login_url="login")
def customer_order_all_picked_up_view(request, pk):
    CustomerOrderPosition.objects.filter(order__production_day=pk).update(
        is_picked_up=True
    )
    return HttpResponseRedirect(
        "{}#orders".format(reverse("workshop:production-day-detail", kwargs={"pk": pk}))
    )


@staff_member_required(login_url="login")
def order_max_quantities_view(request, pk):
    production_day = ProductionDay.objects.get(pk=pk)
    products = {
        Product.objects.get(pk=k.replace("product-", "")): int(v)
        for k, v in request.POST.items()
        if k.startswith("product-")
    }
    products = {}
    for production_day_product in production_day.production_day_products.filter(
        Q(production_plan__state=0) | Q(production_plan__isnull=True)
    ):
        products[production_day_product.product] = (
            production_day_product.calculate_max_quantity(request.user.customer)
        )
    CustomerOrder.create_or_update_customer_order(
        request,
        production_day,
        request.user.customer,
        products,
        request.user.customer.point_of_sale and request.user.customer.point_of_sale.pk,
    )
    return HttpResponseRedirect(
        "{}#orders".format(reverse("workshop:production-day-detail", kwargs={"pk": pk}))
    )


@staff_member_required(login_url="login")
def pos_order_all_picked_up_view(request, production_day, pos):
    CustomerOrderPosition.objects.filter(
        order__production_day=production_day, order__point_of_sale=pos
    ).update(is_picked_up=True)
    return HttpResponseClientRefresh()


class ProductionPlanDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductionPlan

    def get_success_url(self):
        return reverse("workshop:production-plan-next")


class CategoryListView(StaffPermissionsMixin, ListView):
    model = Category

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.get_root_nodes()
        return context


class CategoryAddView(StaffPermissionsMixin, CreateView):
    model = Category
    form_class = movenodeform_factory(
        model, exclude=["slug", "image", "description", "is_archived"]
    )
    success_url = reverse_lazy("workshop:category-list")


class CategoryUpdateView(StaffPermissionsMixin, UpdateView):
    model = Category
    form_class = movenodeform_factory(
        model, exclude=["slug", "image", "description", "is_archived"]
    )
    success_url = reverse_lazy("workshop:category-list")


class CategoryDeleteView(StaffPermissionsMixin, DeleteView):
    model = Category
    success_url = reverse_lazy("workshop:category-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        context["deletable_objects"] = deletable_objects
        context["model_count"] = dict(model_count).items()
        context["protected"] = protected
        return context


class TagListView(StaffPermissionsMixin, ListView):
    model = Tag
    template_name = "workshop/tag_list.html"

    def get_queryset(self) -> QuerySet[Any]:
        qs = (
            super()
            .get_queryset()
            .annotate(num_times=Count("taggit_taggeditem_items"))
            .order_by(Lower("name"))
        )
        return qs


class TagAddView(StaffPermissionsMixin, CreateView):
    model = Tag
    success_url = reverse_lazy("workshop:tag-list")
    fields = ["name", "slug"]
    template_name = "workshop/tag_form.html"


class TagUpdateView(StaffPermissionsMixin, UpdateView):
    model = Tag
    success_url = reverse_lazy("workshop:tag-list")
    fields = ["name", "slug"]
    template_name = "workshop/tag_form.html"


class TagDeleteView(StaffPermissionsMixin, DeleteView):
    model = Tag
    success_url = reverse_lazy("workshop:tag-list")
    template_name = "workshop/tag_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        context["deletable_objects"] = deletable_objects
        context["model_count"] = dict(model_count).items()
        context["protected"] = protected
        return context


class CustomerOrderCreationMixin(object):
    extra_formset = 0

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.get_production_day().has_production_plan_started:
            messages.add_message(
                request,
                messages.WARNING,
                _(
                    "At least one of the production plans for this day has already"
                    " started. You might change a already running production!"
                ),
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        note = self.get_object_note()
        if self.request.POST:
            context["note_form"] = NoteForm(self.request.POST, instance=note)
            context["formset"] = CustomerOrderPositionFormSet(
                self.request.POST,
                form_kwargs={
                    "production_day_products": Product.objects.filter(
                        production_days__production_day=self.get_production_day()
                    )
                },
            )
        else:
            context["note_form"] = NoteForm(instance=note)
            context["formset"] = CustomerOrderPositionFormSet(
                queryset=self.get_object_positions(),
                form_kwargs={
                    "production_day_products": Product.objects.filter(
                        production_days__production_day=self.get_production_day()
                    )
                },
            )
            context["formset"].extra = self.extra_formset
        context["production_day"] = self.get_production_day()
        return context

    def get_production_day(self):
        return self.object.production_day

    def get_object_positions(self):
        return self.object.positions.all()

    def get_object_note(self):
        return Note.objects.filter(
            content_type__model="customerorder", object_id=self.object.id
        ).first()

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        formset = CustomerOrderPositionFormSet(request.POST)
        note = self.get_object_note()
        note_form = NoteForm(request.POST, instance=note)
        form = self.get_form()
        if formset.is_valid() and form.is_valid() and note_form.is_valid():
            return self.form_valid(form, formset, note_form)
        else:
            return self.form_invalid(form, formset, note_form)

    def form_valid(self, form, formset, note_form):
        with transaction.atomic():
            customer_order = form.save(commit=False)
            if not customer_order.point_of_sale:
                customer_order.point_of_sale = self.request.user.customer.point_of_sale
            customer_order.production_day = self.get_production_day()
            customer_order.save()
            if note_form.instance.pk:  # Check if the note already exists
                # If the note exists, update it
                note = note_form.save()
            else:
                # If the note doesn't exist, create a new one
                note = note_form.save(commit=False)
                note.user = self.request.user
                note.content_object = customer_order
                note.save()
            if formset.has_changed():
                instances = formset.save(commit=False)
                for obj in formset.deleted_objects:
                    obj.delete()
                for instance in instances:
                    instance.order = customer_order
                    if instance.production_plan:
                        instance.product = instance.production_plan.product
                    instance.save()
        return HttpResponseRedirect(reverse("workshop:order-list"))


class CustomerOrderUpdateView(
    StaffPermissionsMixin, CustomerOrderCreationMixin, UpdateView
):
    model = CustomerOrder
    fields = ["point_of_sale"]
    template_name = "workshop/customerorder_form.html"
    success_url = reverse_lazy("workshop:order-list")
    extra_formset = 1

    def form_invalid(self, form, formset, note_form):
        if form.errors:
            messages.error(self.request, form.errors)
        if formset.errors:
            messages.error(self.request, formset.errors)
        if note_form.errors:
            messages.error(self.request, note_form.errors)
        return self.render_to_response(self.get_context_data())


class CustomerOrderCreateView(
    StaffPermissionsMixin, CustomerOrderCreationMixin, CreateView
):
    model = CustomerOrder
    form_class = CustomerOrderForm
    template_name = "workshop/customerorder_form.html"
    success_url = reverse_lazy("workshop:order-list")
    extra_formset = 1

    def get_object(self, queryset=None):
        return None

    def get_object_note(self):
        return None

    def get_object_positions(self):
        return CustomerOrderPosition.objects.none()

    def get_production_day(self):
        if "production_day" in self.kwargs:
            return ProductionDay.objects.get(pk=self.kwargs.get("production_day"))
        return None

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        initial["production_day"] = self.get_production_day().pk
        return initial

    def form_invalid(self, form, formset, note_form):
        if form.errors:
            messages.error(self.request, form.errors)
        if formset.errors:
            messages.error(self.request, formset.errors)
        if note_form.errors:
            messages.error(self.request, note_form.errors)
        return self.render_to_response(self.get_context_data())


@staff_member_required(login_url="login")
def production_day_redirect_view(request):
    if request.method == "POST":
        form = ProductionPlanDayForm(request.POST)
        if form.is_valid():
            url = reverse(
                "workshop:production-day-detail",
                kwargs={"pk": form.cleaned_data["production_day"].pk},
            )
            return HttpResponseRedirect(url)
    production_day = ProductionDay.objects.upcoming().first()
    if not production_day:
        production_day = ProductionDay.objects.all().first()
    if production_day:
        url = reverse(
            "workshop:production-day-detail", kwargs={"pk": production_day.pk}
        )
    else:
        url = reverse("workshop:production-day-add")
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
        for point_of_sale in PointOfSale.objects.filter(
            customer_orders__production_day=self.object
        ).distinct():
            positions = CustomerOrderPosition.objects.exclude(
                Q(production_plan__state=ProductionPlan.State.CANCELED)
                | Q(production_plan__isnull=True)
            ).filter(
                order__point_of_sale=point_of_sale, order__production_day=self.object
            )
            order_summary = positions.values("product__name").annotate(
                quantity=Sum("quantity")
            )
            # raise Exception(order_summary)
            orders = CustomerOrder.objects.filter(
                point_of_sale=point_of_sale, production_day=self.object
            ).order_by("customer__user__last_name")
            # raise Exception(positions)
            point_of_sales.append(
                {
                    "point_of_sale": point_of_sale,
                    "orders": orders,
                    "summary": order_summary,
                    "all_picked_up": not CustomerOrderPosition.objects.filter(
                        order__production_day=self.object,
                        order__point_of_sale=point_of_sale,
                        is_picked_up=False,
                    ).exists(),
                }
            )
        # raise Exception(point_of_sales)
        context["point_of_sales"] = point_of_sales
        context["production_day_form"] = ProductionPlanDayForm(
            initial={"production_day": self.object}
        )
        try:
            context["production_day_prev"] = ProductionDay.get_previous_by_day_of_sale(
                self.object
            )
        except ProductionDay.DoesNotExist:
            pass
        try:
            context["production_day_next"] = ProductionDay.get_next_by_day_of_sale(
                self.object
            )
        except ProductionDay.DoesNotExist:
            pass
        context["has_plans_to_start"] = ProductionPlan.objects.filter(
            production_day=self.object,
            state=ProductionPlan.State.PLANNED,
            parent_plan__isnull=True,
        ).exists()
        context["has_plans_to_finish"] = ProductionPlan.objects.filter(
            production_day=self.object,
            state=ProductionPlan.State.IN_PRODUCTION,
            parent_plan__isnull=True,
        ).exists()
        return context


#
class ProductionDayMixin(object):
    extra_formset = 1

    def get_data(self):
        return self.request.POST

    def get_formset_initial(self):
        return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["formset"] = ProductionDayProductFormSet(self.request.POST)
            context["form"] = ProductionDayForm(
                instance=self.object, data=self.request.POST
            )
        else:
            production_day_products = self.get_production_day_products()
            context["formset"] = ProductionDayProductFormSet(
                queryset=production_day_products, initial=self.get_formset_initial()
            )
            context["formset"].extra = self.extra_formset
            context["form"] = ProductionDayForm(
                instance=self.object, initial=self.get_initial()
            )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        formset = ProductionDayProductFormSet(self.get_data())
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
            # raise Exception(instances)
            for obj in formset.deleted_objects:
                try:
                    if obj.production_plan:
                        obj.production_plan.delete()
                    if obj.order_positions.exists():
                        print("redirect....")
                        return HttpResponseRedirect(
                            reverse(
                                "workshop:production-day-product-delete",
                                kwargs={"pk": obj.pk},
                            )
                        )
                    obj.delete()
                except ProtectedError as e:
                    messages.error(self.request, e)
            for instance in instances:
                instance.production_day = production_day
                instance.save()
        production_day.create_template_orders(self.request)
        production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
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
            "workshop:production-day-next",
        )


class ProductionDayProductDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductionDayProduct
    template_name = "workshop/productiondayproduct_confirm_delete.html"

    def setup(self, request, *args, **kwargs):
        return super().setup(request, *args, **kwargs)

    def get_success_url(self):
        return reverse(
            "workshop:production-day-detail",
            kwargs={"pk": self.object.production_day.pk},
        )

    def form_valid(self, form):
        for position in self.object.order_positions.all():
            position.delete()
            if position.order.positions.count() == 0:
                position.order.delete()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


class ProductionDayAddView(NextUrlMixin, ProductionDayMixin, CreateView):
    template_name = "workshop/productionday_form.html"
    model = ProductionDay
    form_class = ProductionDayForm

    def get_production_day_products(self):
        return ProductionDayProduct.objects.filter(production_day=self.object)

    def get_next_page(self):
        return reverse("workshop:production-day-detail", kwargs={"pk": self.object.pk})

    def get_object(self, queryset=None):
        return None


class ProductionDayCopyView(NextUrlMixin, ProductionDayMixin, CreateView):
    template_name = "workshop/productionday_form.html"
    model = ProductionDay
    form_class = ProductionDayForm
    copy_from = None

    @property
    def extra_formset(self):
        return self.copy_from.production_day_products.count()

    def get_data(self):
        post = self.request.POST
        # post._mutable = True
        # for key in post:
        #     if key.endswith("-id"):
        #         post[key] = None
        # post._mutable = False
        return post

    def get(self, request, *args, **kwargs):
        self.copy_from = ProductionDay.objects.get(pk=kwargs.get("pk"))
        return super().get(request, *args, **kwargs)

    def get_formset_initial(self):
        initial = []
        for product in self.copy_from.production_day_products.all():
            initial.append(
                {
                    "product": product.product,
                    "max_quantity": product.max_quantity,
                    "is_published": product.is_published,
                    "group": product.group,
                }
            )
        return initial

    def get_initial(self):
        initial = super().get_initial()
        if self.copy_from:
            initial.update(
                {
                    "description": self.copy_from.description,
                }
            )
        return initial

    def get_production_day_products(self):
        return ProductionDayProduct.objects.none()

    def get_next_page(self):
        return reverse("workshop:production-day-detail", kwargs={"pk": self.object.pk})

    def get_object(self, queryset=None):
        return None


class ProductionDayUpdateView(ProductionDayMixin, UpdateView):
    template_name = "workshop/productionday_form.html"
    model = ProductionDay
    form_class = ProductionDayForm
    extra_formset = 0

    def get_production_day_products(self):
        return ProductionDayProduct.objects.filter(production_day=self.object)

    def get_success_url(self):
        return reverse("workshop:production-day-detail", kwargs={"pk": self.object.pk})


class ProductionDayDeleteView(StaffPermissionsMixin, DeleteView):
    model = ProductionDay
    template_name = "workshop/productionday_confirm_delete.html"

    def get_object(self):
        object = super().get_object()
        if object.is_locked:
            raise Http404()
        return object

    def get_success_url(self):
        return reverse(
            "workshop:production-day-next",
        )


@staff_member_required(login_url="login")
def reminder_message_redirect_view(request, pk):
    production_day = ProductionDay.objects.get(pk=pk)
    if request.method == "POST":
        form = SelectReminderMessageForm(request.POST, production_day=production_day)
        if form.is_valid():
            message = form.cleaned_data["message"]
            if message:
                url = reverse(
                    "workshop:production-day-reminder",
                    kwargs={
                        "production_day": pk,
                        "pk": form.cleaned_data["message"].pk,
                    },
                )
            else:
                url = reverse(
                    "workshop:production-day-reminder", kwargs={"production_day": pk}
                )
            return HttpResponseRedirect(url)
    return HttpResponseRedirect(reverse("workshop:"))


class DummyOrder(object):
    point_of_sale = "Laden"
    total_quantity = 3
    price_total = 12.5

    def get_order_positions_string(self, html=False):
        return """
            1 x Hasenbrot 3,99 € <br>
            2 x Baguette <br>
            1 x Roggenmisch <br>
        """


class ProductionDayReminderView(StaffPermissionsMixin, NextUrlMixin, UpdateView):
    form_class = ReminderMessageForm
    model = ReminderMessage
    template_name = "workshop/productionday_reminder.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["select_message_form"] = self.get_select_message_form()
        context["production_day"] = self.production_day
        context["emails"] = {}
        for point_of_sale in PointOfSale.objects.all():
            context["emails"][point_of_sale.pk] = list(
                self.production_day.customer_orders.filter(
                    point_of_sale=point_of_sale
                ).values_list("customer__user__email", flat=True)
            )

        context["emails"]["all"] = list(
            self.production_day.customer_orders.all().values_list(
                "customer__user__email", flat=True
            )
        )
        context["messages_sent"] = ReminderMessage.objects.filter(
            production_day=self.production_day, state=ReminderMessage.State.SENT
        )
        context["messages_sending"] = ReminderMessage.objects.filter(
            production_day=self.production_day,
            state__in=(
                ReminderMessage.State.PLANNED_SENDING,
                ReminderMessage.State.SENDING,
            ),
        )
        return context

    def get_select_message_form(self):
        initial = {}
        if self.object:
            initial["message"] = self.object.pk
        return SelectReminderMessageForm(
            production_day=self.production_day, initial=initial
        )

    def get_object(self, queryset=None):
        self.production_day = ProductionDay.objects.get(
            pk=self.kwargs.get("production_day")
        )
        try:
            pk = self.kwargs.get(self.pk_url_kwarg)
            return ReminderMessage.objects.get(
                pk=pk, state=ReminderMessage.State.PLANNED
            )
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
            initial.update(
                {
                    "subject": email_settings.get_subject_with_prefix(
                        email_settings.production_day_reminder_subject
                    ),
                    "body": email_settings.production_day_reminder_body,
                }
            )
        initial["production_day"] = self.production_day
        return initial

    def post(self, request: HttpRequest, *args: str, **kwargs: Any) -> HttpResponse:
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        super().form_valid(form)
        if "send" in self.request.POST:
            messages.add_message(
                self.request,
                messages.SUCCESS,
                "Reminder message saved and will be send to selected orders.",
            )
            self.object.set_state_to_planned_sending()
        elif "send_test" in self.request.POST:
            client = connection.get_tenant()
            self.object.send_email(self.request.user, DummyOrder(), client)
        else:
            messages.add_message(
                self.request, messages.SUCCESS, "Reminder message saved."
            )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self, *args, **kwargs):
        # if 'save' in self.request.POST:
        #     return reverse_lazy('workshop:production-day-detail', kwargs={'pk': self.production_day.pk})
        # else:
        return reverse_lazy(
            "workshop:production-day-reminder",
            kwargs={"production_day": self.production_day.pk, "pk": self.object.pk},
        )


class ProductionDayReminderDeleteView(StaffPermissionsMixin, DeleteView):
    model = ReminderMessage

    def get_success_url(self, *args, **kwargs):
        return reverse_lazy(
            "workshop:production-day-reminder",
            kwargs={"production_day": self.kwargs.get("production_day")},
        )


class ProductionDayMetaProductView(StaffPermissionsMixin, NextUrlMixin, CreateView):
    model = CustomerOrder
    fields = [
        "customer",
    ]
    template_name = "workshop/production_day_meta_product_form.html"
    production_day = None
    success_url = reverse_lazy("workshop:production-day-list")

    def dispatch(self, request, *args, **kwargs):
        self.production_day = ProductionDay.objects.get(pk=kwargs.get("pk"))
        self.object = self.production_day
        return super().dispatch(request, *args, **kwargs)

    def get_formset_initial(self):
        initial = []
        for meta_product in Product.objects.filter(
            category__name__iexact=settings.META_PRODUCT_CATEGORY_NAME
        ):
            initial_meta_product = {
                "meta_product": meta_product.pk,
                "meta_product_name": meta_product,
                "product": None,
            }
            initial.append(initial_meta_product)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["production_day"] = self.production_day
        if self.request.POST:
            context["formset"] = ProductionDayMetaProductformSet(
                self.request.POST,
                initial=self.get_formset_initial(),
                form_kwargs={"production_day": self.production_day},
            )
        else:
            context["formset"] = ProductionDayMetaProductformSet(
                initial=self.get_formset_initial(),
                form_kwargs={"production_day": self.production_day},
            )
        context["product_mappings"] = ProductMapping.latest_product_mappings(3)
        return context

    def post(self, request, *args, **kwargs):
        formset = ProductionDayMetaProductformSet(
            request.POST, form_kwargs={"production_day": self.production_day}
        )
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            raise Exception(formset.errors)
            return self.form_invalid(formset)

    def form_valid(self, formset):
        with transaction.atomic():
            meta_product_mapping = {}
            for form in formset:
                meta_product = Product.objects.get(pk=form.cleaned_data["meta_product"])
                product = form.cleaned_data["product"]
                if product:
                    product_mapping, created = ProductMapping.objects.get_or_create(
                        source_product=meta_product,
                        target_product=product,
                        production_day=self.production_day,
                    )
                    meta_product_mapping[meta_product] = {
                        "target_product": product,
                        "product_mapping": product_mapping,
                        "count": 0,
                    }
            for customer in Customer.objects.exclude(order_templates__isnull=True):
                if CustomerOrder.objects.filter(
                    customer=customer, production_day=self.production_day
                ).exists():
                    continue
                positions = CustomerOrderTemplatePosition.objects.active().filter(
                    order_template__customer=customer, quantity__gt=0
                )
                for customer_order_template_position in positions:
                    if meta_product_mapping.get(
                        customer_order_template_position.product, None
                    ):
                        customer_order, created = CustomerOrder.objects.get_or_create(
                            production_day=self.production_day,
                            customer=customer,
                            defaults={"point_of_sale": customer.point_of_sale},
                        )
                        product = meta_product_mapping[
                            customer_order_template_position.product
                        ]["target_product"]
                        price = None
                        price_total = None
                        if product.sale_price:
                            price = product.sale_price.price.amount
                            price_total = (
                                price * customer_order_template_position.quantity
                            )
                        # TODO Q(product=product) | ... and switch to update_or_create
                        position, created = CustomerOrderPosition.objects.get_or_create(
                            order=customer_order,
                            product=product,
                            defaults={
                                "quantity": customer_order_template_position.quantity,
                                "price": price,
                                "price_total": price_total,
                            },
                        )
                        if not created:
                            position.quantity = (
                                position.quantity
                                + customer_order_template_position.quantity
                            )
                            position.save(update_fields=["quantity"])
                        product_mapping = meta_product_mapping[
                            customer_order_template_position.product
                        ]["product_mapping"]
                        product_mapping.matched_count = (
                            product_mapping.matched_count or 0
                        ) + 1
                        product_mapping.save(update_fields=["matched_count"])

        return HttpResponseRedirect(self.get_success_url())


class CustomerListView(
    StaffPermissionsMixin, TableExportMixin, SingleTableMixin, FilterView
):
    model = Customer
    table_class = CustomerTable
    filterset_class = CustomerFilter
    template_name = "workshop/customer_list.html"

    @property
    def export_name(self):
        return "customers-{}".format(now().strftime("%Y%m%d-%H%M%S"))


class CustomerDeleteView(StaffPermissionsMixin, DeleteView):
    model = User
    template_name = "workshop/customer_confirm_delete.html"

    def get_success_url(self):
        return reverse(
            "workshop:customer-list",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        context["deletable_objects"] = deletable_objects
        context["model_count"] = dict(model_count).items()
        context["protected"] = protected
        return context

    def post(self, request, *args, **kwargs):
        return self.delete(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        for protected_object in protected:
            protected_object.force_delete = True
            protected_object.delete()
        success_url = self.get_success_url()
        try:
            self.object.delete()
        except ProtectedError as e:
            messages.error(request, e)
        finally:
            return redirect(success_url)


class CustomerDetailView(StaffPermissionsMixin, DetailView):
    model = Customer
    template_name = "workshop/customer_detail.html"


class CustomerUpdateView(StaffPermissionsMixin, UpdateView):
    template_name = "workshop/customer_form.html"
    model = Customer
    # fields = ['point_of_sale', 'user__first_name']
    form_class = CustomerForm
    success_url = reverse_lazy("workshop:customer-list")

    def get_initial(self):
        initial = super().get_initial()
        initial["first_name"] = self.object.user.first_name
        initial["last_name"] = self.object.user.last_name
        initial["is_active"] = self.object.user.is_active
        initial["groups"] = [i.id for i in self.object.user.groups.all()]
        return initial

    def form_valid(self, form):
        self.object = form.save()
        self.object.user.first_name = form.cleaned_data["first_name"]
        self.object.user.last_name = form.cleaned_data["last_name"]
        self.object.user.is_active = form.cleaned_data["is_active"]
        self.object.user.groups.set(form.cleaned_data["groups"])
        self.object.user.save(update_fields=["first_name", "last_name", "is_active"])
        return HttpResponseRedirect(self.get_success_url())


class CustomerOrderListView(
    StaffPermissionsMixin, TableExportMixin, SingleTableMixin, FilterView
):
    model = CustomerOrder
    table_class = CustomerOrderTable
    filterset_class = CustomerOrderFilter
    template_name = "workshop/order_list.html"

    @property
    def export_name(self):
        return "orders-{}".format(now().strftime("%Y%m%d-%H%M%S"))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_add_order"] = SelectProductionDayForm()
        return context


class GroupDeleteView(StaffPermissionsMixin, DeleteView):
    model = Group
    template_name = "workshop/group_confirm_delete.html"

    def get_success_url(self):
        return reverse(
            "workshop:group-list",
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


class GroupListView(StaffPermissionsMixin, SingleTableView):
    model = Group
    table_class = GroupTable
    template_name = "workshop/group_list.html"

    # @property
    # def export_name(self):
    #     return "orders-{}".format(now().strftime("%Y%m%d-%H%M%S"))

    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context['form_add_order'] = SelectProductionDayForm()
    #     return context


class GroupCreateView(StaffPermissionsMixin, CreateView):
    model = Group
    fields = ("name",)
    template_name = "workshop/group_form.html"
    success_url = reverse_lazy("workshop:group-list")


class GroupUpdateView(StaffPermissionsMixin, UpdateView):
    model = Group
    fields = ("name",)
    template_name = "workshop/group_form.html"
    success_url = reverse_lazy("workshop:group-list")


class CustomerOrderBatchView(StaffPermissionsMixin, NextUrlMixin, CreateView):
    model = CustomerOrder
    fields = [
        "customer",
    ]
    template_name = "workshop/batch_customerorder_form.html"
    production_day = None
    success_url = reverse_lazy("workshop:production-day-list")

    def dispatch(self, request, *args, **kwargs):
        if "pk" not in kwargs and not request.POST.get("select_production_day", None):
            return HttpResponseRedirect(reverse("workshop:order-list"))
        if "pk" not in kwargs:
            return HttpResponseRedirect(
                reverse(
                    "workshop:order-batch",
                    kwargs={"pk": request.POST.get("select_production_day")},
                )
            )
        self.production_day = ProductionDay.objects.get(pk=kwargs.get("pk"))
        self.object = ProductionDay.objects.get(pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def get_formset_initial(self):
        initial = []
        for customer in Customer.objects.all():
            initial_customer = {
                "customer": customer.pk,
                "customer_name": "{} ({})".format(customer, customer.user.email),
            }
            for product in self.production_day.production_day_products.all():
                quantity = None
                customer_order_position = CustomerOrderPosition.objects.filter(
                    Q(product=product.product)
                    | Q(product__product_template=product.product),
                    order__customer=customer,
                    order__production_day=self.production_day,
                )
                if customer_order_position.exists():
                    quantity = customer_order_position.first().quantity
                initial_customer["product_{}".format(product.product.pk)] = quantity
            initial.append(initial_customer)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["production_day"] = self.production_day
        if self.request.POST:
            context["formset"] = BatchCustomerOrderFormSet(
                self.request.POST,
                initial=self.get_formset_initial(),
                form_kwargs={"production_day": self.production_day},
            )
        else:
            context["formset"] = BatchCustomerOrderFormSet(
                initial=self.get_formset_initial(),
                form_kwargs={"production_day": self.production_day},
            )
        return context

    def post(self, request, *args, **kwargs):
        formset = BatchCustomerOrderFormSet(
            request.POST, form_kwargs={"production_day": self.production_day}
        )
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        with transaction.atomic():
            for form in formset:
                customer = form.cleaned_data["customer"]
                customer = Customer.objects.get(pk=customer)
                products = {
                    k: v
                    for k, v in form.cleaned_data.items()
                    if k.startswith("product_")
                }
                # if customer.pk == 2:
                #     raise Exception(not any([v and v > 0 for v in products.values()]))
                if not any([v and v > 0 for v in products.values()]):
                    CustomerOrder.objects.filter(
                        production_day=self.production_day, customer=customer
                    ).delete()
                    continue
                customer_order, created = CustomerOrder.objects.get_or_create(
                    production_day=self.production_day,
                    customer=customer,
                    defaults={"point_of_sale": customer.point_of_sale},
                )
                for product in Product.objects.filter(
                    production_days__production_day=self.production_day
                ):
                    quantity = form.cleaned_data["product_%s" % (product.pk,)]
                    if not quantity or quantity == 0:
                        CustomerOrderPosition.objects.filter(
                            Q(product=product) | Q(product__product_template=product),
                            order=customer_order,
                        ).delete()
                    else:
                        price = None
                        price_total = None
                        if product.sale_price:
                            price = product.sale_price.price.amount
                            price_total = price * quantity
                        position, created = CustomerOrderPosition.objects.filter(
                            Q(product=product) | Q(product__product_template=product)
                        ).update_or_create(
                            order=customer_order,
                            defaults={
                                "product": product,
                                "quantity": quantity,
                                "price": price,
                                "price_total": price_total,
                            },
                        )
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, formset):
        for form_error in formset.errors:
            if form_error:
                messages.error(self.request, form_error)
        if formset.non_form_errors():
            messages.error(self.request, formset.non_form_errors())
        return self.render_to_response(self.get_context_data())


class CustomerOrderDeleteView(StaffPermissionsMixin, DeleteView):
    model = CustomerOrder
    template_name = "workshop/customerorder_confirm_delete.html"

    def get_success_url(self):
        return reverse(
            "workshop:order-list",
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
    fields = ["instruction"]

    def get_object(self, queryset=None):
        obj, created = Instruction.objects.get_or_create(
            product__pk=self.kwargs["pk"],
            defaults={"product": Product.objects.get(pk=self.kwargs["pk"])},
        )
        return obj

    def get_success_url(self):
        return reverse("workshop:product-detail", kwargs={"pk": self.kwargs["pk"]})


class BatchCustomerTemplateView(StaffPermissionsMixin, CreateView):
    model = CustomerOrderTemplate
    fields = [
        "customer",
    ]
    template_name = "workshop/batch_customerordertemplate_form.html"

    def get_formset_initial(self):
        initial = []
        for customer in Customer.objects.all():
            initial_customer = {
                "customer": str(customer.pk),
                "customer_name": "{} ({})".format(customer, customer.user.email),
            }
            for product in Product.objects.filter(is_recurring=True):
                quantity = None
                customer_order_template_position = (
                    CustomerOrderTemplatePosition.objects.active().filter(
                        Q(product=product) | Q(product__product_template=product),
                        order_template__customer=customer,
                    )
                )
                if customer_order_template_position.exists():
                    quantity = customer_order_template_position.first().quantity
                initial_customer["product_{}".format(product.pk)] = quantity
            initial.append(initial_customer)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["formset"] = BatchCustomerOrderTemplateFormSet(
                self.request.POST, initial=self.get_formset_initial()
            )
        else:
            context["formset"] = BatchCustomerOrderTemplateFormSet(
                initial=self.get_formset_initial()
            )
        return context

    def post(self, request, *args, **kwargs):
        formset = BatchCustomerOrderTemplateFormSet(
            request.POST, initial=self.get_formset_initial()
        )
        if formset.is_valid():
            return self.form_valid(formset)
        else:
            return self.form_invalid(formset)

    def form_valid(self, formset):
        with transaction.atomic():
            for form in formset:
                if form.has_changed():
                    customer = form.cleaned_data["customer"]
                    customer = Customer.objects.get(pk=customer)
                    # raise Exception(form.changed_data, self.request.POST, self.get_formset_initial())
                    products_recurring = {
                        Product.objects.get(pk=k.replace("product_", "")): int(
                            form.cleaned_data.get(
                                "product_{}".format(k.replace("product_", ""))
                            )
                        )
                        for k, v in form.cleaned_data.items()
                        if k.startswith("product_") and v
                    }
                    CustomerOrderTemplate.create_customer_order_template(
                        self.request,
                        customer,
                        products_recurring,
                    )
        return HttpResponseRedirect(reverse("workshop:customer-list"))

    def form_invalid(self, formset):
        return self.render_to_response(self.get_context_data())


class PointOfSaleCreateView(StaffPermissionsMixin, CreateView):
    model = PointOfSale
    fields = ("name", "short_name", "is_primary")
    template_name = "workshop/point_of_sale_form.html"

    def get_success_url(self):
        return reverse("workshop:point-of-sale-list")


class PointOfSaleListView(StaffPermissionsMixin, SingleTableView):
    model = PointOfSale
    table_class = PointOfSaleTable
    template_name = "workshop/point_of_sale_list.html"


class PointOfSaleUpdateView(StaffPermissionsMixin, UpdateView):
    model = PointOfSale
    fields = ("name", "short_name", "is_primary")
    template_name = "workshop/point_of_sale_form.html"

    def get_success_url(self):
        return reverse("workshop:point-of-sale-list")


class PointOfSaleDeleteView(StaffPermissionsMixin, DeleteView):
    model = PointOfSale
    template_name = "workshop/point_of_sale_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deletable_objects, model_count, protected = get_deleted_objects([self.object])
        context["deletable_objects"] = deletable_objects
        context["model_count"] = dict(model_count).items()
        context["protected"] = protected
        return context

    def get_success_url(self):
        return reverse("workshop:point-of-sale-list")


class CustomerOrderTemplateOverview(StaffPermissionsMixin, SingleTableView):
    template_name = "workshop/customerorder_template_overview.html"
    model = Product
    table_class = CustomerOrderTemplateTable

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(is_recurring=True, is_sellable=True)
        return qs


class CustomSelect2ViewMixin(Select2ViewMixin):
    def get_results(self, context):
        return [
            {
                "id": self.get_result_value(result),
                "text": self.get_result_label(result),
                "selected_text": self.get_selected_result_label(result),
                "disabled": self.is_disabled_choice(result),
            }
            for result in context["object_list"]
        ]


class CustomSelect2QuerySetView(CustomSelect2ViewMixin, BaseQuerySetView):
    """Adds ability to pass a disabled property to a choice."""


class CustomerAutocomplete(CustomSelect2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated and not self.request.user.is_staff:
            return Customer.objects.none()

        qs = Customer.objects.all()

        if self.q:
            qs = qs.filter(
                Q(user__first_name__istartswith=self.q)
                | Q(user__last_name__istartswith=self.q)
            )
        qs = qs.order_by(Lower("user__last_name"), Lower("user__first_name"))

        return qs

    def get_create_option(self, context, q):
        return []

    def get_result_label(self, item):
        if self.is_disabled_choice(item):
            return f"{item.user} (Bestellung existiert bereits)"
        return f"{item.user}"

    def is_disabled_choice(self, item):
        production_day = self.forwarded.get("production_day", None)
        if item and production_day:
            return item.orders.filter(production_day=production_day).exists()
        return False
