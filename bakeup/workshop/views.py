import calendar
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, OrderedDict
from urllib.parse import quote, unquote, urlencode

from dal.views import BaseQuerySetView
from dal_select2.views import Select2ViewMixin
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Count, ProtectedError, Q, Sum, prefetch_related_objects
from django.db.models.functions import Coalesce, Lower
from django.db.models.query import QuerySet
from django.http import Http404, HttpResponse, HttpResponseRedirect, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.datastructures import MultiValueDict
from django.utils.dates import WEEKDAYS_ABBR
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
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
from django_tables2 import SingleTableMixin, SingleTableView
from django_tables2.export import ExportMixin as TableExportMixin
from taggit.models import Tag
from treebeard.forms import movenodeform_factory

from bakeup.contrib.forms import NoteForm
from bakeup.contrib.models import Note
from bakeup.contrib.notes import can_change_note, get_note_target
from bakeup.core.models import UOM
from bakeup.core.utils import get_deleted_objects
from bakeup.core.views import GetNextPageMixin, NextUrlMixin, StaffPermissionsMixin
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
    UNIT_GRAM,
    UNIT_PERCENT,
    AddIngredientForm,
    CustomerCreateForm,
    CustomerForm,
    CustomerOrderForm,
    PointOfSaleForm,
    PointOfSalePickupTimeFormSet,
    ProductDoughYieldForm,
    ProductForm,
    ProductHierarchyForm,
    ProductionDayMetaProductformSet,
    ProductionPlanDayForm,
    ProductKeyFiguresForm,
    ProductPreFermentForm,
    ProductSaltForm,
    ProductTotalDoughWeightForm,
    ReminderMessageForm,
    SelectProductForm,
    SelectProductionDayForm,
    WaterTemperatureForm,
    ingredient_choices,
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
    prefetch_recipe_trees,
)
from bakeup.workshop.recipe_tools import get_heat_capacity_categories
from bakeup.workshop.reminders import (
    duplicate_mail,
    fill_reminder,
    get_day_orders,
    get_default_text,
    get_mail_recipients,
    get_notified,
    get_points,
    get_preview_order,
    get_reminder_badge,
    get_reminder_overview,
    get_selection,
    queue_mail,
    resolve_recipients,
    store_selection,
    take_back_mail,
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
    ProductionPlanFilter,
    ProductTable,
)
from bakeup.workshop.templatetags.workshop_tags import clever_rounding


class WorkshopView(StaffPermissionsMixin, TemplateView):
    template_name = "workshop/workshop.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recipies_count"] = Product.objects.filter(is_sellable=True).count()
        context["products_count"] = Product.objects.filter(is_sellable=False).count()
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

    def get_initial(self):
        initial = super().get_initial()
        if "sellable" in self.request.GET:
            initial["is_sellable"] = True
        return initial

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


class ProductCopyView(ProductAddView):
    original_product = None
    original_product_name = None
    original_children = None

    def dispatch(self, request, *args, **kwargs):
        if "pk_copy" in kwargs:
            self.original_product = get_object_or_404(
                Product, pk=self.kwargs.get("pk_copy")
            )
            if self.original_product:
                self.original_product_name = self.original_product.name
                self.original_children = list(self.original_product.parents.all())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["original_product"] = self.original_product
        context["original_product_name"] = self.original_product_name
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.original_product:
            kwargs["instance"] = self.original_product
            if self.original_product.name:
                kwargs["instance"].name = f"{self.original_product.name} (Kopie)"
            if self.original_product.display_name:
                kwargs[
                    "instance"
                ].display_name = f"{self.original_product.display_name} (Kopie)"
            kwargs["instance"].sku = ""
        return kwargs

    def form_valid(self, form):
        # Ensure we create a NEW product instead of updating the original
        form.instance.pk = None
        form.instance.id = None
        response = super().form_valid(form)
        # Duplicate the children of the original product for the new product
        for child in self.original_children:
            duplicate_child = Product.duplicate(child.child)
            ProductHierarchy.objects.create(
                parent=form.instance, child=duplicate_child, quantity=child.quantity
            )
        return response


RECIPE_MODE_SESSION_KEY = "recipe_mode"


def is_percent_mode(request, product):
    # In the baker's percentage mode the total flour is the fixed value,
    # otherwise the total dough weight. A recipe without flour has no
    # percentages, it stays in grams.
    return request.session.get(RECIPE_MODE_SESSION_KEY) == UNIT_PERCENT and bool(
        product.total_weight_flour
    )


@staff_member_required(login_url="login")
@require_POST
def product_recipe_mode_view(request, pk):
    product = get_object_or_404(Product, pk=pk)
    request.session[RECIPE_MODE_SESSION_KEY] = (
        UNIT_PERCENT if request.POST.get("mode") == UNIT_PERCENT else UNIT_GRAM
    )
    return redirect(product.get_absolute_url())


MAIN_FLOUR_SESSION_KEY = "main_flours"
INGREDIENT_ORDER_SESSION_KEY = "ingredient_orders"


def get_main_flour(request, product):
    # The main flour balances the flour changes in the baker's percentage
    # mode. It defaults to the largest flour, which is remembered so it doesn't
    # change while the flours are edited.
    flours = product.get_flour_children()
    if not flours:
        return None
    main_flours = request.session.get(MAIN_FLOUR_SESSION_KEY, {})
    main_flour = next(
        (child for child in flours if child.pk == main_flours.get(str(product.pk))),
        None,
    )
    if main_flour is None:
        main_flour = max(flours, key=lambda child: child.weight)
        main_flours[str(product.pk)] = main_flour.pk
        request.session[MAIN_FLOUR_SESSION_KEY] = main_flours
    return main_flour


@staff_member_required(login_url="login")
@require_POST
def product_main_flour_view(request, pk):
    product = get_object_or_404(Product, pk=pk).load_recipe_tree()
    hierarchy = product.parents.filter(pk=request.POST.get("hierarchy")).first()
    if hierarchy and hierarchy in product.get_flour_children():
        main_flours = request.session.get(MAIN_FLOUR_SESSION_KEY, {})
        main_flours[str(product.pk)] = hierarchy.pk
        request.session[MAIN_FLOUR_SESSION_KEY] = main_flours
    return redirect(product.get_absolute_url())


def ratio_error_message(product):
    if not product.total_weight_flour:
        return _("Percentages refer to the flour weight, please add flour first.")
    return _("This percentage can't be reached.")


@staff_member_required(login_url="login")
@require_POST
def product_add_inline_view(request, pk):
    parent_product = get_object_or_404(Product, pk=pk).load_recipe_tree()
    form = AddIngredientForm(request.POST, product=parent_product)
    if form.is_valid():
        added = False
        with transaction.atomic():
            product = form.cleaned_data["product"]
            if product is None:
                product = Product.objects.create(
                    name=form.cleaned_data["new_name"],
                    category=form.cleaned_data["category"],
                    weight=1000,
                    uom=UOM.get_default(),
                )
            if is_percent_mode(request, parent_product):
                # The row starts with a tiny weight, so it doesn't change the
                # total flour the percentage refers to.
                main_flour = get_main_flour(request, parent_product)
                hierarchy = parent_product.add_child(
                    product, 1e-6 / product.weight_in_base_unit
                )
                added = parent_product.adjust_child_ratio(
                    hierarchy,
                    form.cleaned_data["weight"],
                    keep_total_weight=False,
                    balancing=main_flour,
                )
            else:
                parent_product.add_child(
                    product, form.cleaned_data["weight"] / product.weight_in_base_unit
                )
                added = True
            if not added:
                transaction.set_rollback(True)
        if not added:
            messages.error(request, ratio_error_message(parent_product))
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect(parent_product.get_absolute_url())


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
        if form.cleaned_data["unit"] == UNIT_PERCENT:
            self.object.parent.load_recipe_tree()
            percent_mode = is_percent_mode(self.request, self.object.parent)
            if not self.object.parent.adjust_child_ratio(
                self.object,
                amount,
                keep_total_weight=not percent_mode,
                balancing=percent_mode
                and get_main_flour(self.request, self.object.parent),
            ):
                messages.error(self.request, ratio_error_message(self.object.parent))
        elif amount and self.object.child.weight_in_base_unit:
            self.object.quantity = amount / self.object.child.weight_in_base_unit
            self.object.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Please enter a valid weight."))
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("workshop:product-detail", kwargs={"pk": self.object.parent.pk})


class ProductDetailView(StaffPermissionsMixin, DetailView):
    model = Product

    def get_object(self, queryset=None):
        return super().get_object(queryset).load_recipe_tree()

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

    def get_ingredients(self):
        # The ingredients are sorted by weight on a page load. Updates via htmx
        # keep that order, so rows don't jump while they are edited, new rows
        # are appended. The order is sorted again on request.
        ingredients = self.object.get_children_by_weight()
        orders = self.request.session.get(INGREDIENT_ORDER_SESSION_KEY, {})
        order = orders.get(str(self.object.pk))
        if self.request.htmx and order and not self.request.GET.get("sort"):
            position = {pk: index for index, pk in enumerate(order)}
            kept = sorted(
                (child for child in ingredients if child.pk in position),
                key=lambda child: position[child.pk],
            )
            added = sorted(
                (child for child in ingredients if child.pk not in position),
                key=lambda child: child.pk,
            )
            ordered = kept + added
        else:
            ordered = ingredients
        orders[str(self.object.pk)] = [child.pk for child in ordered]
        self.request.session[INGREDIENT_ORDER_SESSION_KEY] = orders
        return ordered, ordered != ingredients

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ingredients"], context["ingredients_unsorted"] = self.get_ingredients()
        context["add_ingredient_form"] = AddIngredientForm(product=self.object)
        context["percent_mode"] = is_percent_mode(self.request, self.object)
        if context["percent_mode"]:
            main_flour = get_main_flour(self.request, self.object)
            context["main_flour_pk"] = main_flour and main_flour.pk
            context["flour_pks"] = [
                child.pk for child in self.object.get_flour_children()
            ]
        if self.object.has_recipe:
            context["key_figures_form"] = ProductKeyFiguresForm(
                initial=self.get_key_figures_inital_data()
            )
        return context


def product_normalize_view(request, pk):
    product = Product.objects.get(pk=pk).load_recipe_tree()
    if request.method == "POST":
        form = ProductKeyFiguresForm(request.POST)
        if form.is_valid():
            fermentation_loss = form.cleaned_data["fermentation_loss"]
            product.normalize(fermentation_loss)
        else:
            raise Exception(form.errors)
    return redirect(product.get_absolute_url())


@staff_member_required
@require_POST
def product_dough_yield_view(request, pk):
    product = get_object_or_404(Product, pk=pk).load_recipe_tree()
    form = ProductDoughYieldForm(request.POST)
    if not form.is_valid() or not product.adjust_dough_yield(
        form.cleaned_data["dough_yield"],
        keep_total_weight=not is_percent_mode(request, product),
    ):
        messages.error(
            request,
            _("Dough yield can't be reached by changing the water on this level."),
        )
    return redirect(product.get_absolute_url())


@staff_member_required
@require_POST
def product_salt_view(request, pk):
    product = get_object_or_404(Product, pk=pk).load_recipe_tree()
    form = ProductSaltForm(request.POST)
    if not form.is_valid() or not product.adjust_salt_ratio(
        form.cleaned_data["salt"],
        keep_total_weight=not is_percent_mode(request, product),
    ):
        messages.error(
            request,
            _("Salt can't be reached by changing the salt on this level."),
        )
    return redirect(product.get_absolute_url())


@staff_member_required
@require_POST
def product_total_dough_weight_view(request, pk):
    product = get_object_or_404(Product, pk=pk).load_recipe_tree()
    form = ProductTotalDoughWeightForm(request.POST)
    if not form.is_valid() or not product.adjust_total_weight(
        form.cleaned_data["total_dough_weight"]
    ):
        messages.error(request, _("Dough weight can't be changed."))
    return redirect(product.get_absolute_url())


@staff_member_required
@require_POST
def product_pre_ferment_view(request, pk):
    product = get_object_or_404(Product, pk=pk).load_recipe_tree()
    form = ProductPreFermentForm(request.POST)
    if not form.is_valid() or not product.adjust_pre_ferment_ratio(
        form.cleaned_data["pre_ferment"],
        keep_total_weight=not is_percent_mode(request, product),
    ):
        messages.error(
            request,
            _(
                "Fermented flour can't be reached by changing the pre dough on this level."
            ),
        )
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
        context["object_name_plural"] = _("Product range")
        context["add_label"] = _("Add new product")
        context["add_url"] = reverse("workshop:product-add") + "?sellable"
        return context


class ProductListView(StaffPermissionsMixin, SingleTableMixin, FilterView):
    model = Product
    table_class = ProductTable
    filterset_class = ProductFilter
    template_name = "workshop/product_list.html"

    def get_queryset(self):
        qs = super().get_queryset()
        # The category and tag links also list the products that are sold.
        if "all" not in self.request.GET:
            qs = qs.filter(is_sellable=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "all" in self.request.GET:
            context["object_name_plural"] = _("All products")
        else:
            context["object_name_plural"] = _("Ingredients & doughs")
        context["add_label"] = _("Add new ingredient")
        context["add_url"] = reverse("workshop:product-add")
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


def get_chosen_steps(request):
    # The dough a baker chose to make next per card, kept per browser in a
    # cookie, see project.js.
    try:
        steps = json.loads(unquote(request.COOKIES.get("production_steps", "{}")))
        return {int(root_pk): int(plan_pk) for root_pk, plan_pk in steps.items()}
    except (ValueError, TypeError, AttributeError):
        return {}


def get_production_plan_cards(production_day, chosen_steps=None):
    # All plans of the day in one query, grouped below their root plan. A card
    # lists the sub plans (pre doughs, main dough, ...) deepest first, which is
    # the order they are made in.
    plans = list(
        ProductionPlan.objects.filter(production_day=production_day)
        .select_related(
            "product__category",
            "product__uom__base_unit",
            "product__product_template",
            "product__instructions",
        )
        .order_by("product__name", "pk")
    )
    prefetch_recipe_trees([plan.product for plan in plans])
    plans_by_pk = {plan.pk: plan for plan in plans}
    for plan in plans:
        if plan.parent_plan_id in plans_by_pk:
            plan.parent_plan = plans_by_pk[plan.parent_plan_id]
    day_products = {
        day_product.product_id: day_product
        for day_product in ProductionDayProduct.objects.filter(
            production_day=production_day
        ).prefetch_related("notes__user")
    }
    # Ordered quantity per product template, "Start" plans exactly this.
    ordered_quantities = {}
    for position in CustomerOrderPosition.objects.filter(
        order__production_day=production_day
    ).values("product_id", "product__product_template_id", "quantity"):
        key = position["product__product_template_id"] or position["product_id"]
        ordered_quantities[key] = ordered_quantities.get(key, 0) + position["quantity"]
    roots = [plan for plan in plans if plan.parent_plan_id is None]
    sub_plans = {root.pk: [] for root in roots}
    # For the water temperature of the steps, see ProductionPlan.get_water.
    categories = get_heat_capacity_categories()
    for plan in plans:
        depth = 0
        root = plan
        while root.parent_plan_id:
            root = root.parent_plan
            depth += 1
        if depth and root.pk in sub_plans:
            sub_plans[root.pk].append((depth, plan))
    cards = []
    for root in roots:
        plans_by_depth = sorted(
            sub_plans[root.pk], key=lambda item: (-item[0], item[1].pk)
        )
        # Ingredients that go into the root product itself (and not via a sub
        # plan) are the last step.
        if any(not row.child.parents.all() for row in root.product.parents.all()):
            plans_by_depth.append((0, root))
        stages = get_production_plan_stages(root, plans_by_depth, categories)
        steps = [step for stage in stages for step in stage["steps"]]
        # In production one dough is made at a time, the first open one. A
        # dough the baker chose comes first until it's done, then the first
        # open one from its stage on, so it doesn't jump back to an earlier one.
        open_steps = [step for step in steps if not step["done"]]
        chosen = next(
            (
                step
                for step in steps
                if step["plan"].pk == (chosen_steps or {}).get(root.pk)
            ),
            None,
        )
        if chosen and not chosen["done"]:
            current = chosen
        else:
            first_stage = chosen["stage"] if chosen else 0
            current = next(
                (step for step in open_steps if step["stage"] >= first_stage),
                open_steps[0] if open_steps else None,
            )
        for step in steps:
            step["is_current"] = root.is_production and step is current
            step["can_choose"] = (
                root.is_production
                and len(steps) > 1
                and not step["done"]
                and not step["is_current"]
            )
        # The dough per piece to divide and weigh out after the last step.
        piece_weight = None
        if steps:
            piece_weight = Product.calculate_total_weight(root.product)
        template = root.product.product_template
        # The plan has its own copy of the instructions, see Product.duplicate.
        instructions = getattr(root.product, "instructions", None)
        rows = [row for step in steps for row in step["rows"]]
        day_product = day_products.get(root.product.product_template_id)
        cards.append(
            {
                # "Start" recreates the plan, the id of the card stays.
                "dom_id": f"card-{day_product.pk}"
                if day_product
                else f"card-plan-{root.pk}",
                "root": root,
                "steps": steps,
                "stages": stages,
                "has_recipe": bool(steps),
                # Without orders "Start" cancels the plan, see _create_production_plan.
                "has_orders": ordered_quantities.get(
                    root.product.product_template_id, 0
                )
                > 0,
                "weight": root.quantity * root.product.weight,
                "piece_weight": piece_weight,
                "total_weight": root.quantity * piece_weight
                if piece_weight
                else root.quantity * root.product.weight,
                "done_count": sum(step["done"] for step in steps),
                "day_product": day_product,
                "product": template,
                "instructions": instructions and instructions.instruction,
                "show_progress": bool(rows)
                and (root.is_production or root.is_produced),
                "row_count": len(rows),
                "checked_count": sum(row["checked"] for row in rows),
            }
        )
    return cards


def get_production_plan_stages(root, plans_by_depth, categories=None):
    # Steps of the same depth can be made at the same time, they form a stage.
    # Stages are numbered in the order they are made, the deepest first.
    stages = []
    for depth, plan in plans_by_depth:
        if not stages or stages[-1]["depth"] != depth:
            stages.append({"depth": depth, "number": len(stages) + 1, "steps": []})
        step = plan.get_step(root, categories)
        step["stage"] = stages[-1]["number"]
        stages[-1]["steps"].append(step)
    steps_by_product = {
        step["plan"].product_id: step for stage in stages for step in stage["steps"]
    }
    for stage in stages:
        if stage["depth"] == 0:
            stage["label"] = _("Main dough")
        else:
            names = []
            for step in stage["steps"]:
                category = step["plan"].product.category
                if category and category.name not in names:
                    names.append(category.name)
            stage["label"] = " · ".join(names) or _("Stage %(number)s") % {
                "number": stage["number"]
            }
        for step in stage["steps"]:
            # A row that is made in another step points to that step.
            for row in step["rows"]:
                row["ref"] = steps_by_product.get(row["row"].child_id)
    return stages


def get_production_plan_doughs(cards):
    """The doughs of the day: how much of each to make, over all products.

    A dough is a step of a plan card, exactly what the card shows to make:
    the sub plans (pre dough, sourdough, ...) and the main dough of the sold
    product itself. Built from the steps of the cards, so plan and doughs
    can't disagree. The same dough in several products is one entry, by its
    template, with its ingredient rows summed up and how it splits over the
    sold products. A dough inside a dough is a step and so an entry of its
    own with its own total. Cancelled plans don't count, started and
    produced ones do, like the ingredient summary.

    The doughs come in groups by their category, in the order they are made:
    the bench order is how deep a dough sits in the plans of the day, the
    deepest first (a starter in a pre dough in the main dough). A category
    comes at the earliest stage of its doughs, ties by name, doughs without
    a category last. Category has no order of its own, the plans give it.
    In a group the deepest dough first, then by name.

    One query of its own, the templates of all ingredient rows at once.
    """
    prefetch_related_objects(
        [
            row["row"].child
            for card in cards
            for step in card["steps"]
            for row in step["rows"]
        ],
        "product_template",
    )
    doughs = {}
    for card in cards:
        root = card["root"]
        if root.is_canceled:
            continue
        sold = root.product.product_template or root.product
        for step in card["steps"]:
            plan = step["plan"]
            depth = 0
            parent = plan
            while parent.parent_plan_id:
                parent = parent.parent_plan
                depth += 1
            template = plan.product.product_template or plan.product
            dough = doughs.setdefault(
                template.pk,
                {
                    "product": template,
                    # The plan's copy has the category of its template and
                    # comes with the cards.
                    "category": plan.product.category,
                    "total": 0,
                    "depth": 0,
                    "uses": {},
                    "rows": {},
                },
            )
            dough["total"] += step["total"]
            dough["depth"] = max(dough["depth"], depth)
            dough["uses"][sold] = dough["uses"].get(sold, 0) + step["total"]
            for row in step["rows"]:
                child = row["row"].child
                child = child.product_template or child
                summed = dough["rows"].setdefault(
                    child.pk, {"product": child, "weight": 0, "unit": row["unit"]}
                )
                summed["weight"] += row["weight"]
    for dough in doughs.values():
        # The main dough of one product goes only into that product, there
        # is nothing to split.
        if list(dough["uses"]) == [dough["product"]]:
            dough["uses"] = {}
        dough["uses"] = [
            {"product": product, "weight": weight}
            for product, weight in sorted(
                dough["uses"].items(), key=lambda item: item[0].name
            )
        ]
        # The heaviest first, like the recipe.
        dough["rows"] = sorted(
            dough["rows"].values(), key=lambda row: row["weight"], reverse=True
        )
    groups = {}
    for dough in sorted(
        doughs.values(), key=lambda dough: (-dough["depth"], dough["product"].name)
    ):
        category = dough["category"]
        group = groups.setdefault(
            category and category.pk,
            {
                "category": category,
                "label": category.name if category else _("Other"),
                "depth": dough["depth"],
                "doughs": [],
            },
        )
        group["doughs"].append(dough)
    return sorted(
        groups.values(),
        key=lambda group: (
            group["category"] is None,
            -group["depth"],
            group["label"],
        ),
    )


def get_production_plan_summary(cards):
    """The figures of the plan at the start of its toolbar.

    Only what the cards don't say: the number of products is the badge of
    the products tab, the state shows on every card (its button, progress or
    badge) and as the dot of the day in the week strip.
    """
    active = [card for card in cards if not card["root"].is_canceled]
    return {
        "pieces": sum(card["root"].quantity for card in active),
        "weight": sum(card["weight"] for card in active),
    }


class ProductionPlanOfProductionDay(StaffPermissionsMixin, TemplateView):
    template_name = "workshop/productionplan_productionday.html"
    production_day = None

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.production_day = get_object_or_404(ProductionDay, pk=kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cards = get_production_plan_cards(
            self.production_day, get_chosen_steps(self.request)
        )
        context["cards"] = cards
        context["summary"] = get_production_plan_summary(cards)
        context["production_day"] = self.production_day
        context["day_switch"] = get_day_switch(self.production_day, "plan")
        # Three views of the plan: the cards, the doughs over all products and
        # the ingredients of all of them, chosen in the toolbar. Printing
        # prints the one on screen.
        context["plan_views"] = [
            {"key": "plan", "label": _("Plan")},
            {"key": "doughs", "label": _("Doughs")},
            {"key": "ingredients", "label": _("Ingredients")},
        ]
        context["doughs"] = get_production_plan_doughs(cards)
        context["plan_actions"] = Actions(
            [Action(_("Print"), icon="fas fa-print", kind="secondary", is_print=True)]
        )
        return context


@require_POST
@staff_member_required(login_url="login")
def production_plan_ingredient_toggle_view(request, pk, row_pk=None):
    # Ticks off one row of a step, without a row all rows of the step.
    plan = get_object_or_404(ProductionPlan, pk=pk)
    root = plan.get_root()
    status = 400
    if root.is_production and row_pk is None:
        plan.toggle_all_ingredients()
        status = 200
    elif root.is_production and plan.product.parents.filter(pk=row_pk).exists():
        plan.toggle_ingredient(row_pk)
        status = 200
    return render_production_plan_steps(request, root, status=status)


@staff_member_required(login_url="login")
def production_plan_steps_view(request, pk):
    # The steps after the baker chose another dough to make next.
    root = get_object_or_404(ProductionPlan, pk=pk, parent_plan=None)
    return render_production_plan_steps(request, root)


@staff_member_required(login_url="login")
def production_plan_water_temperature_view(request, pk):
    # The water temperature calculator of a step, the content of the modal. In
    # every state of the plan, water is tempered before production starts. A
    # change of a field only previews the result, "Apply" saves the
    # temperatures on the plan and "Reset" removes them again.
    plan = get_object_or_404(ProductionPlan.objects.select_related("product"), pk=pk)
    plan.product.load_recipe_tree()
    water = plan.get_water()
    if water is None:
        raise Http404
    if request.method == "POST" and "reset" in request.POST:
        plan.set_temperatures({})
        return render_production_plan_water_temperature_applied(request, plan)
    form = WaterTemperatureForm(
        request.POST if request.method == "POST" else None, water=water
    )
    status = 200
    if request.method == "POST":
        if form.is_valid():
            water = plan.get_water(temperatures=form.get_temperatures())
            if "apply" in request.POST:
                # Always with the dough temperature and the mixer warming, so
                # an applied calculation is never empty.
                plan.set_temperatures(
                    {
                        **form.get_temperatures(),
                        "dough": water["dough"],
                        "warming": water["warming"],
                    }
                )
                return render_production_plan_water_temperature_applied(request, plan)
        else:
            status = 422
    return render(
        request,
        "workshop/includes/production_plan_water_temperature.html",
        {"plan": plan, "water": water, "form": form},
        status=status,
    )


def render_production_plan_water_temperature_applied(request, plan):
    # The modal is not the place of the steps, they are swapped out of band.
    # The event closes the modal, see project.js.
    response = render_production_plan_steps(
        request,
        plan.get_root(),
        template_name="workshop/includes/production_plan_water_temperature_applied.html",
    )
    response["HX-Trigger"] = "closeProductionPlanModal"
    return response


def render_production_plan_steps(
    request,
    root,
    status=200,
    template_name="workshop/includes/production_plan_step_toggled.html",
):
    # All steps of the card, finishing or undoing one moves the current stage,
    # with the header progress, as the page renders them.
    for card in get_production_plan_cards(
        root.production_day, get_chosen_steps(request)
    ):
        if card["root"].pk == root.pk:
            return render(request, template_name, {"card": card}, status=status)
    raise Http404


def render_notes(request, target, form=None, edit_note=None, status=200):
    return render(
        request,
        "workshop/includes/notes.html",
        {"object": target, "form": form, "edit_note": edit_note},
        status=status,
    )


def get_changeable_note(request, pk):
    note = get_object_or_404(Note, pk=pk)
    target = get_note_target(
        f"{note.content_type.app_label}.{note.content_type.model}", note.object_id
    )
    if not can_change_note(request.user, note):
        raise PermissionDenied
    return note, target


@staff_member_required(login_url="login")
def notes_view(request, model, object_id):
    target = get_note_target(model, object_id)
    if request.method == "POST":
        form = NoteForm(request.POST)
        form.fields["content"].required = True
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.content_object = target
            note.save()
            return render_notes(request, target)
        return render_notes(request, target, form=form, status=422)
    edit_note = None
    if request.GET.get("edit", "").isdigit():
        edit_note, target = get_changeable_note(request, request.GET["edit"])
    return render_notes(request, target, edit_note=edit_note)


@require_POST
@staff_member_required(login_url="login")
def note_update_view(request, pk):
    note, target = get_changeable_note(request, pk)
    form = NoteForm(request.POST, instance=note)
    form.fields["content"].required = True
    if form.is_valid():
        form.save()
        return render_notes(request, target)
    return render_notes(request, target, form=form, edit_note=note, status=422)


@require_POST
@staff_member_required(login_url="login")
def note_delete_view(request, pk):
    note, target = get_changeable_note(request, pk)
    note.delete()
    return render_notes(request, target)


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
    for production_plan in filter(None, production_plans_updated):
        production_plan.production_day.update_order_positions_product(
            production_plan.product
        )
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(reverse("workshop:production-plan-next"))


@staff_member_required(login_url="login")
def production_plan_start_view(request, pk):
    production_plan = ProductionPlan.objects.get(pk=pk)
    production_day = production_plan.production_day
    if production_plan.get_next_state() == ProductionPlan.State.IN_PRODUCTION:
        production_plan = production_day.create_or_update_production_plan(
            product=production_plan.product.product_template,
            state=ProductionPlan.State.IN_PRODUCTION,
            create_max_quantity=False,
        )
        if production_plan:
            production_day.update_order_positions_product(production_plan.product)
    if "next" in request.GET:
        return HttpResponseRedirect(request.GET.get("next"))
    return HttpResponseRedirect(
        reverse(
            "workshop:production-plan-production-day",
            kwargs={"pk": production_day.pk},
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
    # The new order is in the orders of the day.
    return HttpResponseRedirect(
        "{}#orders".format(reverse("workshop:production-day-detail", kwargs={"pk": pk}))
    )


@staff_member_required(login_url="login")
def pos_order_all_picked_up_view(request, production_day, pos):
    """Ticks all orders of a point of sale, or none when all are ticked."""
    production_day = get_object_or_404(ProductionDay, pk=production_day)
    point_of_sale = get_object_or_404(PointOfSale, pk=pos)
    positions = CustomerOrderPosition.objects.filter(
        order__production_day=production_day, order__point_of_sale=point_of_sale
    )
    positions.update(is_picked_up=positions.filter(is_picked_up=False).exists())
    # Back to the orders with the point of sale still chosen.
    return HttpResponseRedirect(
        f"{production_day.get_absolute_url()}?pickup={point_of_sale.pk}#orders"
    )


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
                    obj.order.skip_abo([obj])
                    obj.delete()
                for instance in instances:
                    instance.order = customer_order
                    if instance.production_plan:
                        instance.product = instance.production_plan.product
                    instance.save()
        # From the orders of a day they go back there, e.g. its pane.
        return HttpResponseRedirect(
            self.get_next_page() or reverse("workshop:order-list")
        )


class CustomerOrderUpdateView(
    StaffPermissionsMixin, GetNextPageMixin, CustomerOrderCreationMixin, UpdateView
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
    StaffPermissionsMixin, GetNextPageMixin, CustomerOrderCreationMixin, CreateView
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


@dataclass
class Action:
    """A button or a menu item of a page or a section toolbar.

    Primary and secondary actions are buttons, the others go into the menu.
    """

    label: str
    url: str = ""
    icon: str = ""
    kind: str = "menu"
    color: str = "primary"
    danger: bool = False
    disabled: bool = False
    disabled_reason: str = ""
    is_print: bool = False
    # Runs in place with htmx, the url stays as fallback without JavaScript.
    is_htmx: bool = False
    # A submit button instead of a link: its name, and the id of its form
    # when it sits outside of it.
    submit_name: str = ""
    # The value the submit button sends with its name.
    submit_value: str = ""
    form: str = ""
    # Asks once more on the first tap, see data-confirm-tap.
    confirm_label: str = ""
    # A number after the label, e.g. the recipients of an email.
    badge: Any = None
    # The id of a panel the button opens instead of acting itself, e.g. the
    # preview of an email with the button that sends it.
    opens: str = ""
    id: str = ""
    # In the orders list: shown only while this point of sale is chosen
    # ("all" for all of them), see data-pickup-only.
    pickup: str = ""

    @property
    def is_submit(self):
        return bool(self.submit_name or self.form)

    @property
    def css_class(self):
        if self.kind == "primary":
            return f"btn-{self.color}"
        return "btn-surface"


class Actions(list):
    @property
    def buttons(self):
        return [action for action in self if action.kind != "menu"]

    @property
    def menu_has_confirm(self):
        # The menu stays open for the second tap.
        return any(action.confirm_label for action in self.menu)

    @property
    def menu(self):
        # Destructive actions come last, the template puts a divider before them.
        return sorted(
            (action for action in self if action.kind == "menu"),
            key=lambda action: action.danger,
        )


def get_production_day_stats(production_day):
    """The figures of the day in the info of its overview. The states of
    the plans are the column of the product table."""
    published = production_day.total_published_quantity
    sold = production_day.total_published_ordered_quantity
    return {
        "orders": production_day.total_orders,
        "pieces": production_day.total_ordered_quantity,
        "published": published,
        "sold": sold,
        "sold_percent": min(100, round(sold * 100 / published)) if published else 0,
        "sales": (
            production_day.total_sales
            if production_day.has_products_with_price()
            else None
        ),
    }


def get_production_day_product_totals(rows):
    """The last row of the product table: how many products, and all their
    orders against all their maximums."""
    ordered = sum(row["ordered"] for row in rows)
    maximum = sum(row["day_product"].max_quantity or 0 for row in rows)
    return {
        "count": len(rows),
        "ordered": ordered,
        "max": maximum,
        "percent": min(100, round(ordered * 100 / maximum)) if maximum else 0,
        "is_over": ordered > maximum,
    }


def get_production_day_product_rows(production_day):
    rows = []
    for day_product in production_day.production_day_products.select_related(
        "product", "group", "production_plan"
    ):
        ordered = day_product.get_order_quantity()
        maximum = day_product.max_quantity or 0
        rows.append(
            {
                "day_product": day_product,
                "ordered": ordered,
                "percent": min(100, round(ordered * 100 / maximum)) if maximum else 0,
                "is_over": ordered > maximum,
            }
        )
    return rows


# The state a production day shows in the calendar, the first one that any
# of its plans has.
CALENDAR_STATE_ORDER = [
    ProductionPlan.State.IN_PRODUCTION,
    ProductionPlan.State.PLANNED,
    ProductionPlan.State.PRODUCED,
    ProductionPlan.State.CANCELED,
]

# Where a day of the calendar or the day switcher leads: the URL name, its
# argument for the day, and the part of that page htmx swaps. The pickup
# emails have an editor that doesn't survive a swap, they load the page.
CALENDAR_LINKS = {
    "day": ("workshop:production-day-detail", "pk", "#production-day-detail"),
    "plan": ("workshop:production-plan-production-day", "pk", "#production-day"),
    "reminder": ("workshop:production-day-reminder", "production_day", None),
}


# The part of the calendar a day page loads, by the parameter that asks for
# it: the calendar in its layer.
CALENDAR_MODE_TEMPLATES = {
    "overlay": "workshop/includes/production_day_calendar.html",
}


def get_production_day_url(production_day, link):
    url_name, kwarg, _target = CALENDAR_LINKS[link]
    return reverse(url_name, kwargs={kwarg: production_day.pk})


def get_calendar_products(production_days):
    """The products of each day with ordered and maximum quantity.

    A position is of the product itself or of its copy in the plan, like in
    ProductionDayProduct.get_order_quantity.
    """
    ordered = {
        (day, product): quantity
        for day, product, quantity in CustomerOrderPosition.objects.filter(
            order__production_day__in=production_days
        )
        .annotate(day_product=Coalesce("product__product_template", "product"))
        .values_list("order__production_day", "day_product")
        .annotate(quantity=Sum("quantity"))
    }
    products = {}
    for day_product in (
        ProductionDayProduct.objects.filter(production_day__in=production_days)
        .select_related("product")
        .order_by("product__name")
    ):
        key = (day_product.production_day_id, day_product.product_id)
        products.setdefault(day_product.production_day_id, []).append(
            {
                "name": day_product.product.name,
                "ordered": ordered.get(key, 0),
                "max": day_product.max_quantity,
            }
        )
    return products


def get_production_day_calendar(month, selected=None, link="day", week=None, mode=None):
    """The weeks of a month with its production days, Monday first.

    With week, any date of it, only that week, with the products of each day.

    The calendar is a page of its own without a mode. The day pages use it in
    two modes that keep their section (link) and their day (selected): "strip"
    is the week of the day in the head of the page, "overlay" the calendar in
    the layer the date of the head opens.
    """
    target = CALENDAR_LINKS[link][2]
    if week:
        monday = week - timedelta(days=week.weekday())
        weeks = [[monday + timedelta(days=offset) for offset in range(7)]]
        # The month the week counts to, the one of its Thursday like the
        # calendar week. The month view opens there.
        month = monday + timedelta(days=3)
    month = month.replace(day=1)
    if not week:
        weeks = calendar.Calendar().monthdatescalendar(month.year, month.month)
    production_days = {
        day.day_of_sale: day
        for day in ProductionDay.objects.filter(
            day_of_sale__range=(weeks[0][0], weeks[-1][-1])
        ).annotate(orders=Count("customer_orders", distinct=True))
    }
    states = {}
    for day_pk, state in ProductionPlan.objects.filter(
        production_day__in=production_days.values(), parent_plan__isnull=True
    ).values_list("production_day", "state"):
        states.setdefault(day_pk, set()).add(state)
    is_strip = mode == "strip"
    products = {} if is_strip else get_calendar_products(production_days.values())
    today = now().date()

    def cell(date):
        production_day = production_days.get(date)
        cell = {
            "date": date,
            "in_month": bool(week) or date.month == month.month,
            "is_today": date == today,
            "is_selected": date == selected,
            "can_add": date >= today,
            "day": production_day,
        }
        if production_day:
            cell["url"] = get_production_day_url(production_day, link)
            day_states = states.get(production_day.pk, set())
            state = next((s for s in CALENDAR_STATE_ORDER if s in day_states), None)
            if state is not None:
                cell["state_label"] = ProductionPlan.state_display_value(state)
                cell["state_css_class"] = ProductionPlan.state_css_class(state)
            if not is_strip:
                cell["sold_percent"] = min(100, production_day.sold_percentage)
                cell["products"] = products.get(production_day.pk, [])
        return cell

    def calendar_url(mode=mode, **params):
        if mode:
            params.update({mode: 1, "link": link})
            if selected:
                params["selected"] = selected.isoformat()
        return reverse("workshop:production-day-calendar") + "?" + urlencode(params)

    def month_url(other, **kwargs):
        return calendar_url(month=other.strftime("%Y-%m"), **kwargs)

    def week_url(other):
        monday = other - timedelta(days=other.weekday())
        return calendar_url(week=monday.isoformat())

    data = {
        "month": month,
        "mode": mode,
        "target": target,
        # Adding a day belongs to the day pages, not to the plan or the emails.
        "can_add_day": link == "day",
        "weekdays": [WEEKDAYS_ABBR[day] for day in range(7)],
        "weeks": [[cell(date) for date in dates] for dates in weeks],
    }
    if week:
        data.update(
            is_week=True,
            week_start=weeks[0][0],
            week_end=weeks[0][-1],
            week_number=weeks[0][0].isocalendar().week,
            previous_url=week_url(weeks[0][0] - timedelta(days=7)),
            next_url=week_url(weeks[0][0] + timedelta(days=7)),
            today_url=week_url(today),
            previous_label=_("Previous week"),
            next_label=_("Next week"),
            month_view_url=month_url(month),
            week_view_url=week_url(weeks[0][0]),
        )
    else:
        previous_month = (month - timedelta(days=1)).replace(day=1)
        next_month = (month + timedelta(days=31)).replace(day=1)
        # The week view opens on this week when the month has it, on the
        # first week of the month otherwise.
        in_month = today.replace(day=1) == month
        data.update(
            is_week=False,
            previous_url=month_url(previous_month),
            next_url=month_url(next_month),
            today_url=month_url(today),
            previous_label=_("Previous month"),
            next_label=_("Next month"),
            month_view_url=month_url(month),
            week_view_url=week_url(today if in_month else month),
        )
    if is_strip:
        # The strip opens the calendar in the layer, on the month of the
        # chosen day. Its page is the fallback without JavaScript.
        opens_on = selected or weeks[0][0]
        data.update(
            overlay_url=month_url(opens_on, mode="overlay"),
            page_url=month_url(opens_on, mode=None),
        )
    return data


def parse_date(value, format):
    try:
        return datetime.strptime(value or "", format).date()
    except ValueError:
        return None


class ProductionDayCalendarView(StaffPermissionsMixin, TemplateView):
    template_name = "workshop/productionday_calendar.html"

    def get_mode(self):
        for mode in CALENDAR_MODE_TEMPLATES:
            if self.request.GET.get(mode):
                return mode

    def get_template_names(self):
        return [CALENDAR_MODE_TEMPLATES.get(self.get_mode(), self.template_name)]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        mode = self.get_mode()
        link = params.get("link") if params.get("link") in CALENDAR_LINKS else "day"
        context["calendar"] = get_production_day_calendar(
            parse_date(params.get("month"), "%Y-%m") or now().date(),
            selected=parse_date(params.get("selected"), "%Y-%m-%d"),
            link=link,
            week=parse_date(params.get("week"), "%Y-%m-%d"),
            mode=mode,
        )
        return context


def get_day_tabs(production_day, active):
    """The sections of a production day, the tab row of its pages.

    Overview and orders are panes of the day page, there they switch without
    loading. The ingredients are a view of the plan, the delivery bill is
    printed from the orders. From the plan and the pickup
    emails they link to the day page, the hash opens the pane.

    Between the day page and the plan htmx swaps the page (swap_url), a full
    load felt slow. The pickup emails load: their editor needs the scripts of
    its page and doesn't survive a swap.

    The orders carry their number, the pickup emails how far they got once
    one is sent. The products are counted in the last row of their table on
    the overview.
    """
    on_day = active == "day"
    day_url = production_day.get_absolute_url()
    # Every order with its point of sale: their number is the badge of the
    # orders, and they tell how far the pickup emails got.
    order_points = list(
        production_day.customer_orders.values_list("pk", "point_of_sale_id")
    )
    tabs = [
        {"key": "overview", "label": _("Overview"), "is_active": on_day},
        {
            "key": "orders",
            "label": _("Orders"),
            "badge": len(order_points),
        },
    ]
    for tab in tabs:
        tab.update(is_pane=on_day, url=f"{day_url}#{tab['key']}")
        if active == "plan":
            tab["swap_url"] = day_url
    for link, label in [
        ("plan", _("Production plan")),
        ("reminder", _("Pickup emails")),
    ]:
        tabs.append(
            {
                "key": link,
                "label": label,
                "url": get_production_day_url(production_day, link),
                "is_active": active == link,
            }
        )
        if link == "reminder":
            badge = get_reminder_badge(production_day, order_points)
            if badge:
                tabs[-1]["badge"] = badge
        if link == "plan":
            if on_day:
                tabs[-1]["swap_url"] = tabs[-1]["url"]
            if is_production_day_produced(production_day):
                tabs[-1]["badge"] = "✓"
    return tabs


def is_production_day_produced(production_day):
    """The day is baked: it has plans and every one that wasn't cancelled is
    produced. The check of the plan tab, like the one of the pickup emails
    when everybody is told."""
    states = set(
        production_day.production_plans.filter(parent_plan__isnull=True)
        .exclude(state=ProductionPlan.State.CANCELED)
        .values_list("state", flat=True)
    )
    return states == {ProductionPlan.State.PRODUCED}


def get_day_actions(production_day, link):
    """The actions of a production day, the same in the head of all its pages.

    Editing is the one quiet button. The one filled button is the next step
    of the day: starting comes first, finishing waits in the menu until
    nothing is left to start. Everything else is in the menu.

    Start and finish run in place on the day page and the plan, the page
    comes back with the plans in their new state. The pickup emails have no
    swap target, there they are links and come back by their next. What takes
    a next comes back to the page it was opened from.
    """
    pk = production_day.pk
    next_url = "?next=" + get_production_day_url(production_day, link)
    plans = ProductionPlan.objects.filter(
        production_day=production_day, parent_plan__isnull=True
    )
    has_plans_to_start = plans.filter(state=ProductionPlan.State.PLANNED).exists()
    has_plans_to_finish = plans.filter(
        state=ProductionPlan.State.IN_PRODUCTION
    ).exists()
    day = {"production_day": pk}
    actions = Actions(
        [
            Action(
                _("Edit"),
                reverse("workshop:production-day-update", kwargs={"pk": pk}) + next_url,
                "fas fa-edit",
                kind="secondary",
            )
        ]
    )
    if has_plans_to_start:
        actions.append(
            Action(
                _("Start all"),
                reverse("workshop:production-plans-start", kwargs=day) + next_url,
                "fas fa-play",
                kind="primary",
                is_htmx=True,
                color="warning",
            )
        )
    if has_plans_to_finish:
        actions.append(
            Action(
                _("Finish all"),
                reverse("workshop:production-plans-finish", kwargs=day) + next_url,
                "fas fa-check",
                kind="menu" if has_plans_to_start else "primary",
                is_htmx=True,
                color="success",
            )
        )
    actions += [
        Action(
            _("New production day"),
            reverse("workshop:production-day-add"),
            "fas fa-plus",
        ),
        Action(
            _("Copy"),
            reverse("workshop:production-day-copy", kwargs={"pk": pk}),
            "fas fa-copy",
        ),
        Action(
            _("Abos"),
            reverse("workshop:production-day-meta-product", kwargs={"pk": pk})
            + next_url,
            "fas fa-retweet",
        ),
        Action(
            _("Export as CSV"),
            reverse("workshop:production-day-export", kwargs={"pk": pk}),
            "fas fa-file-download",
        ),
        Action(
            _("Delete"),
            reverse("workshop:production-day-delete", kwargs={"pk": pk}),
            "fas fa-trash-can",
            danger=True,
            disabled=production_day.is_locked,
            disabled_reason=_("Has orders"),
        ),
    ]
    return actions


def get_current_day_url(production_day, link):
    """The way back to the current production day, the next one from today
    like the sidebar opens it. None on that day itself."""
    current = ProductionDay.objects.upcoming().first() or ProductionDay.objects.first()
    if current and current.pk != production_day.pk:
        return get_production_day_url(current, link)


def get_day_switch(production_day, link):
    """The head of the pages of a production day.

    The date is the title of the page and opens the calendar, beside it the
    way back to the current day. Under it the week of the day as a strip
    with the previous and the next production day at its ends, then the tab
    row. The actions in
    the title row are the same on every page, what belongs to one page is in
    the toolbar of its section. link is the page, the days of the strip and
    of the calendar lead to the same page of another day. The figures of the
    day are on its overview, the ones of the plan in its toolbar.
    """
    day = production_day.day_of_sale
    switch = {
        "production_day": production_day,
        "target": CALENDAR_LINKS[link][2],
        "week": get_production_day_calendar(
            day, selected=day, link=link, week=day, mode="strip"
        ),
        "tabs": get_day_tabs(production_day, link),
        "actions": get_day_actions(production_day, link),
        "current_url": get_current_day_url(production_day, link),
    }
    for key, method in [
        ("previous_url", ProductionDay.get_previous_by_day_of_sale),
        ("next_url", ProductionDay.get_next_by_day_of_sale),
    ]:
        try:
            switch[key] = get_production_day_url(method(production_day), link)
        except ProductionDay.DoesNotExist:
            switch[key] = None
    return switch


def production_day_reminder_redirect_view(request):
    """The pickup emails of the next production day, for the sidebar."""
    production_day = (
        ProductionDay.objects.upcoming().first() or ProductionDay.objects.first()
    )
    if not production_day:
        return HttpResponseRedirect(reverse("workshop:production-day-add"))
    return HttpResponseRedirect(get_production_day_url(production_day, "reminder"))


def get_production_day_phase(production_day):
    """Where the day stands, from the state of its plans.

    "collecting" until a plan is started: the orders are edited. "handing
    out" once any plan is in production or produced, also when others are
    still planned: the orders are packed and picked up. Cancelled plans
    don't count.
    """
    started = production_day.production_plans.filter(
        parent_plan__isnull=True,
        state__in=[ProductionPlan.State.IN_PRODUCTION, ProductionPlan.State.PRODUCED],
    ).exists()
    return "handing_out" if started else "collecting"


# The points of sale of a day are chips in the toolbar of its orders: one
# tap, and the number of orders of each at a glance. More of them than this
# would fill several lines, then they are a dropdown and the toolbar stays
# one row.
PICKUP_CHIPS_MAX = 6


def get_day_order_groups(production_day, bills):
    """The orders list of a day, by point of sale and then by customer, with
    the products of each point. The orders without a point of sale, which
    the delivery bill doesn't print, come last."""
    groups = [
        {
            "key": str(bill["point_of_sale"].pk),
            "label": bill["point_of_sale"].name,
            "chip": bill["point_of_sale"].get_short_name(),
            "orders": bill["orders"],
            "summary": bill["summary"],
        }
        for bill in bills
    ]
    without = list(
        CustomerOrder.objects.filter(
            production_day=production_day, point_of_sale__isnull=True
        )
        .with_is_first_order()
        .select_related("customer__user")
        .prefetch_related("notes", "positions__product", "positions__production_plan")
        .order_by("customer__user__last_name")
    )
    if without:
        groups.append(
            {
                "key": "none",
                "label": _("Without point of sale"),
                "chip": _("Without point of sale"),
                "orders": without,
                "summary": [],
            }
        )
    for group in groups:
        for order in group["orders"]:
            # From the loaded positions, CustomerOrder.is_picked_up asks the
            # database for every order.
            order.picked_up = all(
                position.is_picked_up for position in order.positions.all()
            )
    return groups


def get_unlocked_order_ids(production_day):
    """The orders of the day that can still be changed, as
    CustomerOrder.is_locked decides, in one query for the whole list."""
    return set(
        CustomerOrder.objects.filter(production_day=production_day)
        .filter(
            Q(positions__production_plan__state=ProductionPlan.State.PLANNED)
            | Q(
                positions__production_plan__isnull=True,
                positions__product__parents__isnull=False,
            )
        )
        .values_list("pk", flat=True)
    )


def get_delivery_bills(production_day):
    """The orders of a day by point of sale, for the delivery bills: the
    groups of the orders list and the printed delivery bill."""
    point_of_sales = []
    points_of_sale = (
        PointOfSale.objects.filter(customer_orders__production_day=production_day)
        .distinct()
        .order_by("name")
    )
    for point_of_sale in points_of_sale:
        positions = CustomerOrderPosition.objects.exclude(
            Q(production_plan__state=ProductionPlan.State.CANCELED)
            | Q(production_plan__isnull=True)
        ).filter(
            order__point_of_sale=point_of_sale, order__production_day=production_day
        )
        order_summary = positions.values("product__name").annotate(
            quantity=Sum("quantity")
        )
        orders = list(
            CustomerOrder.objects.filter(
                point_of_sale=point_of_sale, production_day=production_day
            )
            .with_is_first_order()
            .select_related("customer__user")
            .prefetch_related(
                "notes", "positions__product", "positions__production_plan"
            )
            .order_by("customer__user__last_name")
        )
        point_of_sales.append(
            {
                "point_of_sale": point_of_sale,
                "orders": orders,
                # Without any note the column goes, the others get its room.
                "has_notes": any(order.notes.all() for order in orders),
                "summary": order_summary,
                "all_picked_up": not CustomerOrderPosition.objects.filter(
                    order__production_day=production_day,
                    order__point_of_sale=point_of_sale,
                    is_picked_up=False,
                ).exists(),
            }
        )
    return point_of_sales


class ProductionDayDetailView(StaffPermissionsMixin, DetailView):
    model = ProductionDay
    template_name = "workshop/productionday_detail.html"

    def get_orders_url(self):
        # The orders pane, as a next it is quoted: the hash would end the url.
        return quote(f"{self.object.get_absolute_url()}#orders", safe="/")

    def get_orders_actions(self, phase, has_plans_to_start, groups):
        """The toolbar of the orders. Printing the delivery bill is the one
        button, everything else is in the menu: adding and editing orders
        (while handing out still possible for the products not started) and,
        while handing out, marking a point of sale as picked up."""
        pk = self.object.pk
        next_url = f"?next={self.get_orders_url()}"
        handing_out = phase == "handing_out"
        actions = Actions(
            [
                Action(
                    _("Add order"),
                    reverse("workshop:order-add", kwargs={"production_day": pk})
                    + next_url,
                    "fas fa-plus-circle",
                ),
                Action(
                    _("Edit orders"),
                    reverse("workshop:order-batch", kwargs={"pk": pk}) + next_url,
                    "fas fa-edit",
                ),
                Action(
                    _("Print delivery bill"),
                    icon="fas fa-print",
                    kind="secondary",
                    is_print=True,
                ),
            ]
        )
        if has_plans_to_start:
            actions.append(
                Action(
                    _("Order max. quantities"),
                    reverse(
                        "workshop:production-day-order-max-quantities",
                        kwargs={"pk": pk},
                    ),
                    "fas fa-arrow-up-wide-short",
                    is_htmx=True,
                )
            )
        actions.append(
            Action(
                _("Show in order list"),
                reverse("workshop:order-list") + f"?production_day={pk}",
                "fas fa-shopping-basket",
            )
        )
        if handing_out:
            # For the chosen point of sale only, the list shows the one that
            # fits. All points: the whole day is marked as picked up.
            actions.append(
                Action(
                    _("All picked up"),
                    reverse("workshop:production-day-all-picked-up", kwargs={"pk": pk}),
                    "fas fa-square-check",
                    is_htmx=True,
                    pickup="all",
                )
            )
            for group in groups:
                if group["key"] == "none":
                    continue
                all_picked_up = all(order.picked_up for order in group["orders"])
                actions.append(
                    Action(
                        _("None picked up") if all_picked_up else _("All picked up"),
                        reverse(
                            "workshop:pos-all-picked-up",
                            kwargs={"production_day": pk, "pos": group["key"]},
                        ),
                        "far fa-square" if all_picked_up else "fas fa-square-check",
                        is_htmx=True,
                        pickup=group["key"],
                    )
                )
        return actions

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        has_plans_to_start = ProductionPlan.objects.filter(
            production_day=self.object,
            state=ProductionPlan.State.PLANNED,
            parent_plan__isnull=True,
        ).exists()
        # The delivery bill is printed only, by point of sale. The same bills
        # are the groups of the orders list.
        context["point_of_sales"] = get_delivery_bills(self.object)
        phase = get_production_day_phase(self.object)
        groups = get_day_order_groups(self.object, context["point_of_sales"])
        context["phase"] = phase
        context["order_groups"] = groups
        context["pickup_as_select"] = len(groups) > PICKUP_CHIPS_MAX
        context["has_order_notes"] = any(
            order.notes.all() for group in groups for order in group["orders"]
        )
        context["has_prices"] = self.object.has_products_with_price()
        if phase == "handing_out":
            context["unlocked_orders"] = get_unlocked_order_ids(self.object)
            # The packing list of all points, for "all" in the list.
            context["order_summary"] = (
                CustomerOrderPosition.objects.exclude(
                    Q(production_plan__state=ProductionPlan.State.CANCELED)
                    | Q(production_plan__isnull=True)
                )
                .filter(order__production_day=self.object)
                .values("product__name")
                .annotate(quantity=Sum("quantity"))
                .order_by("product__name")
            )
        context["stats"] = get_production_day_stats(self.object)
        context["product_rows"] = get_production_day_product_rows(self.object)
        context["product_totals"] = get_production_day_product_totals(
            context["product_rows"]
        )
        # Editing or deleting an order comes back to the orders pane.
        context["order_next"] = f"{self.object.get_absolute_url()}#orders"
        context["product_mappings"] = list(
            self.object.product_mapping.select_related(
                "source_product", "target_product"
            )
        )
        # The toolbars of the panes are quiet, the one filled button of the
        # page is the next step of the day in its head.
        context["orders_actions"] = self.get_orders_actions(
            phase, has_plans_to_start, groups
        )
        context["day_switch"] = get_day_switch(self.object, "day")
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
        # Abo orders are only created for products that became orderable with
        # this save: added as published, published now, or swapped in. Saving
        # anything else must not bring back orders that were removed.
        products = [
            instance.product_id
            for instance in formset.new_objects
            if instance.is_published
        ] + [
            instance.product_id
            for instance, changed_fields in formset.changed_objects
            if instance.is_published
            and {"is_published", "product"}.intersection(changed_fields)
        ]
        if products:
            positions = production_day.create_template_orders(
                self.request, products=products
            )
            if positions:
                product_names = sorted(
                    {position.product.get_display_name() for position in positions}
                )
                messages.success(
                    self.request,
                    ngettext(
                        "%(count)d abo order created for %(products)s.",
                        "%(count)d abo orders created for %(products)s.",
                        len(positions),
                    )
                    % {"count": len(positions), "products": ", ".join(product_names)},
                )
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
            position.order.skip_abo([position])
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

    def get_initial(self):
        initial = super().get_initial()
        day_of_sale = parse_date(self.request.GET.get("day_of_sale"), "%Y-%m-%d")
        if day_of_sale:
            initial["day_of_sale"] = day_of_sale
        return initial


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


class DummyUser(object):
    first_name = "Manu"
    last_name = "Musteruser"
    email = "manu@example.com"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


# The placeholders of a pickup email, see ReminderMessage.replace_message_tags.
REMINDER_TAGS = [
    "first_name",
    "last_name",
    "order",
    "order_count",
    "price_total",
    "point_of_sale",
    "production_day",
    "order_link",
    "order_link_text",
    "site_name",
    "email",
]


def get_reminder_url(production_day, name="production-day-reminder", **kwargs):
    return reverse(
        f"workshop:{name}", kwargs={"production_day": production_day.pk, **kwargs}
    )


def get_new_reminder_url(production_day, keys=()):
    """The tab with the editor of a new email open, for the points of sale of
    keys (all without). The fallback of the buttons that open it in place."""
    params = QueryDict(mutable=True)
    params["new"] = "1"
    if keys:
        params.setlist("points", list(keys))
    return f"{get_reminder_url(production_day)}?{params.urlencode()}#reminder-editor"


def get_edit_reminder_url(production_day, mail):
    """The tab with the editor of a draft open under its row."""
    return f"{get_reminder_url(production_day)}?edit={mail.pk}#reminder-editor"


def get_reminder_preview(mail, recipients):
    """An email as its first recipient gets it, or as the example customer."""
    return fill_reminder(
        mail,
        mail.production_day,
        connection.get_tenant(),
        get_preview_order(recipients),
        (DummyOrder(), DummyUser()),
    )


@staff_member_required(login_url="login")
def production_day_reminder_preview_view(request, production_day):
    """The email being written in the editor, filled in with the first order
    of the recipients chosen there, or with an example."""
    production_day = get_object_or_404(ProductionDay, pk=production_day)
    orders = get_day_orders(production_day)
    notified = get_notified(production_day, orders)
    form = ReminderMessageForm(request.POST, points=get_points(orders, notified))
    mail = ReminderMessage(
        production_day=production_day,
        subject=form["subject"].value() or "",
        body=form["body"].value() or "",
    )
    selection = (
        set(request.POST.getlist("points"))
        if request.POST.get("recipients") == ReminderMessageForm.POINTS
        else set()
    )
    recipients = resolve_recipients(selection, orders)
    return render(
        request,
        "workshop/includes/reminder_preview.html",
        get_reminder_preview(mail, recipients),
    )


@staff_member_required(login_url="login")
def production_day_reminder_mail_view(request, production_day, pk):
    """An email of the list opened: as its first recipient gets it and who
    it goes or went to."""
    mail = get_object_or_404(
        ReminderMessage.objects.select_related("production_day"),
        pk=pk,
        production_day=production_day,
    )
    orders = get_day_orders(mail.production_day)
    recipients = get_mail_recipients(
        mail, orders, get_notified(mail.production_day, orders)
    )
    return render(
        request,
        "workshop/includes/reminder_mail.html",
        {
            "mail": mail,
            "recipients": [
                order.customer.user.email for order in recipients if order.customer
            ],
            **get_reminder_preview(mail, recipients),
        },
    )


class ProductionDayReminderView(StaffPermissionsMixin, TemplateView):
    """The pickup emails of a day: how many orders were notified, per point
    of sale, a table of its emails and the editor of one email, see
    bakeup/workshop/reminders.py.

    The page has one editor. Without ?edit it is the editor of a new email,
    hidden above the table until "New email" or a chip opens it in place
    (?new=1 opens it without JavaScript). With ?edit=<pk> it is the editor of
    that draft, open under its row. The editor of the text doesn't survive an
    htmx swap, so it comes with the page and is posted with a page load."""

    template_name = "workshop/productionday_reminder.html"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.production_day = get_object_or_404(
            ProductionDay, pk=kwargs["production_day"]
        )

    def get_page_url(self):
        return get_reminder_url(self.production_day)

    def get_mail_actions(self, mail):
        pk = str(mail.pk)
        actions = Actions()
        panel = f"reminder-mail-{pk}"
        if mail.is_planned:
            actions.append(
                Action(
                    _("Edit"),
                    get_edit_reminder_url(self.production_day, mail),
                    "fas fa-pen",
                    kind="secondary",
                )
            )
            # Sending opens the email as it goes out, the button under it
            # sends it.
            actions.append(
                Action(
                    _("Send"),
                    icon="fas fa-paper-plane",
                    kind="secondary",
                    opens=panel,
                    badge=len(mail.recipients),
                    disabled=not mail.recipients,
                )
            )
        else:
            actions.append(
                Action(_("View"), icon="far fa-eye", kind="secondary", opens=panel)
            )
        if mail.is_planned_sending:
            actions.append(
                Action(
                    _("Back to draft"),
                    icon="fas fa-rotate-left",
                    submit_name="take_back",
                    submit_value=pk,
                    form="reminder-send-form",
                )
            )
        if mail.is_planned or mail.is_sent:
            actions.append(
                Action(
                    _("Duplicate"),
                    icon="far fa-copy",
                    submit_name="duplicate",
                    submit_value=pk,
                    form="reminder-send-form",
                )
            )
        if mail.is_planned:
            actions.append(
                Action(
                    _("Delete"),
                    icon="far fa-trash-can",
                    danger=True,
                    submit_name="delete",
                    submit_value=pk,
                    form="reminder-send-form",
                    confirm_label=_("Delete draft?"),
                )
            )
        return actions

    def get_initial(self, mail):
        if mail:
            selection = get_selection(mail)
            text = mail
        else:
            selection = set(self.request.GET.getlist("points"))
            text = get_default_text(self.request, self.production_day)
        return {
            "recipients": ReminderMessageForm.POINTS
            if selection
            else ReminderMessageForm.ALL,
            "points": sorted(selection),
            "subject": text.subject,
            "body": text.body,
        }

    def get_form(self, mail, orders, notified, data=None):
        points = get_points(orders, notified, get_selection(mail) if mail else ())
        instance = mail or ReminderMessage(production_day=self.production_day)
        if data is not None:
            return ReminderMessageForm(data, instance=instance, points=points)
        return ReminderMessageForm(
            instance=instance, initial=self.get_initial(mail), points=points
        )

    def get_editor(self, overview, mail, form, is_open):
        orders = overview["order_list"]
        selection = (
            set(form["points"].value() or [])
            if form["recipients"].value() == ReminderMessageForm.POINTS
            else set()
        )
        count = len(resolve_recipients(selection, orders))
        return {
            "form": form,
            "mail": mail,
            "is_open": is_open,
            "points": form.point_list,
            "selected": set(form["points"].value() or []),
            "is_all": form["recipients"].value() != ReminderMessageForm.POINTS,
            "orders": len(orders),
            "open": len(orders) - overview["notified"],
            "tags": ["{{ %s }}" % tag for tag in REMINDER_TAGS],
            # The label of the button that sends, the number follows the
            # chosen recipients in the browser.
            "send_one": get_send_label(1),
            "send_many": get_send_label(2, "__count__"),
            # The footer: the test email on its own on the left, then from
            # the least to the most final step, the one that sends last.
            # "Cancel" closes the editor of a new email in place while
            # nothing was changed in it, see project.js.
            "cancel_url": self.get_page_url(),
            "send_label": get_send_label(count),
            "test_email": self.request.user.email,
        }

    def get_context_data(self, mail=None, form=None, is_open=False, **kwargs):
        context = super().get_context_data(**kwargs)
        overview = get_reminder_overview(self.production_day, connection.get_tenant())
        for point in overview["points"]:
            # A point with open orders starts an email to them.
            if point["open"]:
                point["url"] = get_new_reminder_url(self.production_day, [point["key"]])
        for item in overview["mails"]:
            item.actions = self.get_mail_actions(item)
            item.send = next(
                (action for action in item.actions if item.is_planned and action.opens),
                None,
            )
        if form is None:
            form = self.get_form(
                mail,
                overview["order_list"],
                overview["notified_ids"],
            )
        editor = self.get_editor(overview, mail, form, is_open or bool(mail))
        context["production_day"] = self.production_day
        context["day_switch"] = get_day_switch(self.production_day, "reminder")
        context["overview"] = overview
        context["editor"] = editor
        context["new_url"] = get_new_reminder_url(self.production_day)
        # "New email" opens the editor in place, or loads the page with it
        # while a draft is edited.
        context["reminder_actions"] = Actions(
            [
                Action(
                    _("New email"),
                    context["new_url"],
                    "fas fa-plus",
                    kind="primary",
                    id="reminder-new",
                )
            ]
        )
        return context

    def get_mail(self, pk, *states):
        return ReminderMessage.objects.filter(
            production_day=self.production_day, pk=pk, state__in=states
        ).first()

    def get_draft(self, pk):
        """The draft of ?edit or the editor's post, None once it was queued
        or sent in the meantime."""
        mail = (
            self.get_mail(pk, *ReminderMessage.State.values) if pk.isdigit() else None
        )
        if mail and not mail.is_planned:
            messages.warning(self.request, _("This email was sent already."))
            return None
        return mail

    def get(self, request, *args, **kwargs):
        if "edit" in request.GET:
            mail = self.get_draft(request.GET["edit"])
            if not mail:
                return HttpResponseRedirect(self.get_page_url())
            return self.render_to_response(self.get_context_data(mail=mail))
        return self.render_to_response(
            self.get_context_data(is_open="new" in request.GET)
        )

    def post(self, request, *args, **kwargs):
        post = request.POST
        if "editor" in post:
            return self.post_editor(post["editor"])
        State = ReminderMessage.State
        if "send" in post:
            mail = self.get_mail(post["send"], State.PLANNED)
            if not mail:
                messages.warning(request, _("This email was sent already."))
                return HttpResponseRedirect(self.get_page_url())
            orders = get_day_orders(self.production_day)
            recipients = get_mail_recipients(
                mail, orders, get_notified(self.production_day, orders)
            )
            if not recipients:
                messages.warning(request, _("There is nobody to send this email to."))
            else:
                queue_mail(mail, recipients)
                messages.success(request, get_queued_message(len(recipients)))
        elif "take_back" in post:
            mail = self.get_mail(post["take_back"], State.PLANNED_SENDING)
            if mail and take_back_mail(mail):
                messages.success(request, _("The email is a draft again."))
            else:
                messages.warning(request, _("The email is being sent already."))
        elif "delete" in post:
            mail = self.get_mail(post["delete"], State.PLANNED)
            if mail:
                mail.delete()
                messages.success(request, _("Draft deleted."))
        elif "duplicate" in post:
            mail = self.get_mail(post["duplicate"], State.PLANNED, State.SENT)
            if mail:
                copy = duplicate_mail(mail)
                return HttpResponseRedirect(
                    get_edit_reminder_url(self.production_day, copy)
                )
        return HttpResponseRedirect(self.get_page_url())

    def post_editor(self, target):
        """The editor saved, sent or tested: "new" or the pk of a draft. On
        an error the page comes again with the editor open where it was."""
        request = self.request
        mail = None
        if target != "new":
            mail = self.get_draft(target)
            if not mail:
                return HttpResponseRedirect(self.get_page_url())
        orders = get_day_orders(self.production_day)
        notified = get_notified(self.production_day, orders)
        form = self.get_form(mail, orders, notified, data=request.POST)

        def again():
            return self.render_to_response(
                self.get_context_data(mail=mail, form=form, is_open=True)
            )

        if not form.is_valid():
            return again()
        recipients = resolve_recipients(form.selection, orders)
        text = form.save(commit=False)
        if "send_test" in request.POST:
            text.send_email(
                request.user,
                get_preview_order(recipients) or DummyOrder(),
                connection.get_tenant(),
            )
            messages.success(
                request,
                _("Test email sent to %(email)s.") % {"email": request.user.email},
            )
            return again()
        if "send" in request.POST and not recipients:
            form.add_error(None, _("Nobody gets this email, choose other recipients."))
            return again()
        text.state = ReminderMessage.State.PLANNED
        text.save()
        store_selection(text, form.selection)
        if "send" in request.POST:
            queue_mail(text, recipients)
            messages.success(request, get_queued_message(len(recipients)))
        else:
            messages.success(request, _("Draft saved."))
        return HttpResponseRedirect(self.get_page_url())


def get_queued_message(count):
    return ngettext(
        "The email will be sent to %(count)s order in a moment.",
        "The email will be sent to %(count)s orders in a moment.",
        count,
    ) % {"count": count}


def get_send_label(count, shown=None):
    return ngettext("Send to %(count)s order", "Send to %(count)s orders", count) % {
        "count": count if shown is None else shown
    }


class ProductionDayMetaProductView(StaffPermissionsMixin, NextUrlMixin, CreateView):
    model = CustomerOrder
    fields = [
        "customer",
    ]
    template_name = "workshop/production_day_meta_product_form.html"
    production_day = None

    def get_success_url(self):
        return self.get_next_page() or self.production_day.get_absolute_url()

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

    def get_queryset(self):
        return super().get_queryset().with_first_order_date()

    @property
    def export_name(self):
        return "customers-{}".format(now().strftime("%Y%m%d-%H%M%S"))


class CustomerCreateView(StaffPermissionsMixin, CreateView):
    model = Customer
    form_class = CustomerCreateForm
    template_name = "workshop/customer_form.html"
    success_url = reverse_lazy("workshop:customer-list")

    def form_valid(self, form):
        from allauth.account.models import EmailAddress

        email = form.cleaned_data["email"]
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            is_active=True,
            password=None,
        )
        user.groups.set(form.cleaned_data["groups"])
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        customer = user.customer
        customer.point_of_sale = form.cleaned_data.get("point_of_sale")
        customer.street = form.cleaned_data.get("street", "")
        customer.street_number = form.cleaned_data.get("street_number", "")
        customer.postal_code = form.cleaned_data.get("postal_code", "")
        customer.city = form.cleaned_data.get("city", "")
        customer.telephone_number = form.cleaned_data.get("telephone_number", "")
        customer.save()
        self.object = customer
        if form.cleaned_data.get("send_invite"):
            from allauth.account.forms import ResetPasswordForm

            reset_form = ResetPasswordForm(data={"email": email})
            if reset_form.is_valid():
                reset_form.save(self.request)
        return HttpResponseRedirect(self.get_success_url())


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

    def get_queryset(self):
        return super().get_queryset().with_first_order_date()


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

    def get_queryset(self):
        return super().get_queryset().with_is_first_order()

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

    def get_success_url(self):
        return self.get_next_page() or self.production_day.get_absolute_url()

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
                    for customer_order in CustomerOrder.objects.filter(
                        production_day=self.production_day, customer=customer
                    ):
                        customer_order.skip_abo()
                        customer_order.delete()
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
                        positions = CustomerOrderPosition.objects.filter(
                            Q(product=product) | Q(product__product_template=product),
                            order=customer_order,
                        )
                        customer_order.skip_abo(list(positions))
                        positions.delete()
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


class CustomerOrderDeleteView(StaffPermissionsMixin, GetNextPageMixin, DeleteView):
    model = CustomerOrder
    template_name = "workshop/customerorder_confirm_delete.html"

    def get_success_url(self):
        return self.get_next_page() or reverse("workshop:order-list")

    def form_valid(self, form):
        # DeleteView deletes in form_valid, it does not call delete().
        success_url = self.get_success_url()
        try:
            # A protected order rolls back to here and leaves no skip behind.
            with transaction.atomic():
                self.object.skip_abo()
                self.object.delete()
        except ProtectedError as e:
            messages.error(self.request, e)
        return redirect(success_url)


class CreateUpdateInstructionsView(StaffPermissionsMixin, UpdateView):
    model = Instruction
    fields = ["instruction"]

    def get_object(self, queryset=None):
        obj, created = Instruction.objects.get_or_create(
            product__pk=self.kwargs["pk"],
            defaults={"product": Product.objects.get(pk=self.kwargs["pk"])},
        )
        return obj

    def get_template_names(self):
        # htmx requests edit the instructions inline on the product page.
        if self.request.htmx:
            return ["workshop/includes/instructions.html"]
        return super().get_template_names()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product"] = self.object.product
        context.setdefault(
            "editing", self.request.method == "POST" or "edit" in self.request.GET
        )
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.htmx:
            return self.render_to_response(
                self.get_context_data(form=form, editing=False)
            )
        return HttpResponseRedirect(self.get_success_url())

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
                        create_future_production_day_orders=True,
                    )
        return HttpResponseRedirect(reverse("workshop:customer-list"))

    def form_invalid(self, formset):
        return self.render_to_response(self.get_context_data())


class PointOfSaleFormMixin:
    """The point of sale form together with the formset of its pick-up times."""

    model = PointOfSale
    form_class = PointOfSaleForm
    template_name = "workshop/point_of_sale_form.html"

    def get_pickup_time_formset(self):
        return PointOfSalePickupTimeFormSet(
            self.request.POST or None, instance=self.object, prefix="pickup_times"
        )

    def get_context_data(self, **kwargs):
        if "pickup_time_formset" not in kwargs:
            kwargs["pickup_time_formset"] = self.get_pickup_time_formset()
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        pickup_time_formset = self.get_pickup_time_formset()
        if not pickup_time_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(
                    form=form, pickup_time_formset=pickup_time_formset
                )
            )
        with transaction.atomic():
            self.object = form.save()
            pickup_time_formset.instance = self.object
            pickup_time_formset.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse("workshop:point-of-sale-list")


class PointOfSaleCreateView(PointOfSaleFormMixin, StaffPermissionsMixin, CreateView):
    pass


class PointOfSaleListView(StaffPermissionsMixin, SingleTableView):
    model = PointOfSale
    table_class = PointOfSaleTable
    template_name = "workshop/point_of_sale_list.html"


class PointOfSaleUpdateView(PointOfSaleFormMixin, StaffPermissionsMixin, UpdateView):
    pass


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


class IngredientAutocomplete(Select2ViewMixin, BaseQuerySetView):
    def get_queryset(self):
        if not self.request.user.is_staff:
            return Product.objects.none()
        parent = Product.objects.filter(pk=self.forwarded.get("parent")).first()
        qs = ingredient_choices(parent)
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs.order_by(Lower("name"))

    def get_create_option(self, context, q):
        q = (q or "").strip()
        if (
            not q
            or self.request.GET.get("page", "1") != "1"
            or Product.objects.filter(name__iexact=q).exists()
        ):
            return []
        return [
            {
                "id": f"{AddIngredientForm.NEW_PREFIX}{q}",
                "text": _('Create "%(name)s"') % {"name": q},
            }
        ]


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
