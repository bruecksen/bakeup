import logging
from datetime import datetime
from typing import Any, List

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import CharField, Exists, F, Func, OuterRef, Q, Subquery, Value
from django.db.models.query import QuerySet
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.timezone import make_aware
from django.views.generic import DeleteView, ListView, TemplateView

from bakeup.contrib.calenderweek import CalendarWeek
from bakeup.core.views import CustomerRequiredMixin
from bakeup.pages.models import EmailSettings
from bakeup.shop.models import (
    CustomerOrder,
    CustomerOrderPosition,
    CustomerOrderTemplate,
    CustomerOrderTemplatePosition,
    PointOfSale,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.workshop.models import Product

logger = logging.getLogger(__name__)

# Limit orders in the future
MAX_FUTURE_ORDER_YEARS = 2


class ProductListView(ListView):
    model = Product
    template_name = "shop/product_list.html"

    def get_queryset(self) -> QuerySet[Any]:
        today = timezone.now().date()
        return (
            Product.objects.filter(
                is_sellable=True,
                production_days__is_published=True,
                production_days__production_day__day_of_sale__gte=today,
            )
            .distinct()
            .order_by("category")
        )


class ProductionDayListView(ListView):
    model = ProductionDay
    template_name = "shop/production_day_list.html"

    def get_queryset(self) -> QuerySet[Any]:
        return super().get_queryset().upcoming()


class ProductionDayWeeklyView(CustomerRequiredMixin, TemplateView):
    template_name = "shop/weekly.html"

    def dispatch(self, request, *args, **kwargs):
        self.calendar_week_current = CalendarWeek.current()
        self.calendar_week = self.get_calendar_week()
        if self.calendar_week is None:
            # fallback to current  week
            return redirect(
                reverse(
                    "shop:weekly",
                    kwargs={
                        "year": self.calendar_week_current.year,
                        "calendar_week": self.calendar_week_current.week,
                    },
                )
            )
        return super().dispatch(request, *args, **kwargs)

    def get_calendar_week(self):
        if "calendar_week" in self.kwargs and "year" in self.kwargs:
            input_week = self.kwargs.get("calendar_week")
            input_year = self.kwargs.get("year")
            if (
                0 < input_week <= 53
                and 2000
                < input_year
                <= timezone.now().date().year + MAX_FUTURE_ORDER_YEARS
            ):
                return CalendarWeek(input_week, input_year)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.calendar_week and self.calendar_week != self.calendar_week_current:
            # only if we are showing a calender week that is not the current one
            # we need a jump to current link
            context["calendar_week_current"] = self.calendar_week_current
        context["calendar_week"] = self.calendar_week

        production_days = ProductionDay.objects.filter(
            day_of_sale__week=self.calendar_week.week,
            day_of_sale__year=self.calendar_week.year,
        )
        forms = {}
        customer = (
            None if self.request.user.is_anonymous else self.request.user.customer
        )
        for production_day in production_days:
            production_day_products = []
            for production_day_product in production_day.production_day_products.all():
                form = production_day_product.get_order_form(customer)
                production_day_products.append(
                    {"production_day_product": production_day_product, "form": form}
                )
            forms[production_day] = production_day_products

        context["production_days"] = forms
        return context


@login_required
def customer_order_add_or_update(request, production_day):
    if request.method == "POST":
        next_url = request.POST.get("next_url", None)
        production_day = get_object_or_404(ProductionDay, pk=production_day)
        if "create" in request.POST or "update" in request.POST:
            # create or update order
            products = {
                Product.objects.get(pk=k.replace("product-", "")): int(v)
                for k, v in request.POST.items()
                if k.startswith("product-")
            }
            order, created, changes_detected = (
                CustomerOrder.create_or_update_customer_order(
                    request,
                    production_day,
                    request.user.customer,
                    products,
                    request.POST.get("point_of_sale", None),
                )
            )
            products_recurring = {
                Product.objects.get(pk=k.replace("productabo-", "")): int(
                    request.POST.get("product-{}".format(k.replace("productabo-", "")))
                )
                for k, v in request.POST.items()
                if k.startswith("productabo-")
            }
            if products_recurring:
                CustomerOrderTemplate.create_customer_order_template(
                    request,
                    request.user.customer,
                    products_recurring,
                    production_day,
                    True,
                )
            if order and created:
                messages.add_message(
                    request, messages.INFO, "Vielen Dank für die Bestellung."
                )
            elif order and not created:
                messages.add_message(
                    request,
                    messages.INFO,
                    "Vielen Dank, die Bestellung wurde geändert.",
                )
            if order and changes_detected:
                if EmailSettings.load(request_or_site=request).send_email_order_confirm:
                    order.send_order_confirm_email(request)
            return HttpResponseRedirect(
                "{}#bestellung-{}".format(reverse("shop:order-list"), order.pk)
            )
        elif "cancel" in request.POST:
            # cancellation of order
            customer_order = get_object_or_404(
                CustomerOrder,
                production_day=production_day,
                customer=request.user.customer,
            )
            logger.error("Order #%s: order will be completely deleted!", customer_order)
            email = None
            if EmailSettings.load(
                request_or_site=request
            ).send_email_order_cancellation:
                email = customer_order.generate_order_cancellation_email(request)
            customer_order.delete()
            if email:
                try:
                    email.send(fail_silently=False)
                except Exception as e:
                    logger.error(
                        "Order #%s: Error while sending cancellation email: %s",
                        customer_order,
                        e,
                    )
            messages.add_message(
                request,
                messages.INFO,
                "Bestellung vom {} erfolgreich storniert.".format(production_day),
            )
            return HttpResponseRedirect(reverse("shop:order-list"))

        if next_url:
            return HttpResponseRedirect(next_url)
        else:
            return HttpResponseRedirect("/shop/")


class CustomerOrderListView(CustomerRequiredMixin, ListView):
    model = CustomerOrder
    template_name = "shop/customer_order_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["point_of_sales"] = PointOfSale.objects.all()
        context["next_url"] = reverse_lazy("shop:order-list")
        context["abos"] = CustomerOrderTemplate.objects.active().filter(
            customer=self.request.user.customer
        )
        return context

    def get_queryset(self):
        return super().get_queryset().filter(customer=self.request.user.customer)


class CustomerOrderTemplateListView(CustomerRequiredMixin, ListView):
    model = CustomerOrderTemplate
    template_name = "shop/customer_order_template_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["point_of_sales"] = PointOfSale.objects.all()
        return context

    def get_queryset(self):
        return (
            super().get_queryset().active().filter(customer=self.request.user.customer)
        )


class CustomerOrderTemplateDeleteView(CustomerRequiredMixin, DeleteView):
    model = CustomerOrderTemplate
    template_name = "shop/customer_order_template_delete.html"

    def delete(self, request, *args, **kwargs):
        """
        Call the delete() method on the fetched object and then redirect to the
        success URL.
        """
        self.object = self.get_object()
        success_url = self.get_success_url()
        self.object.cancel()
        messages.add_message(self.request, messages.INFO, "Abo erfolgreich beendet!")
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return reverse_lazy("shop:order-list")


@login_required
def customer_order_template_update(request, pk):
    if request.method == "POST":
        get_object_or_404(CustomerOrderTemplate, pk=pk)
        products_recurring = {
            Product.objects.get(pk=k.replace("productabo-", "")): int(
                request.POST.get("productabo-{}".format(k.replace("productabo-", "")))
            )
            for k, v in request.POST.items()
            if k.startswith("productabo-")
        }
        if products_recurring:
            CustomerOrderTemplate.create_customer_order_template(
                request,
                request.user.customer,
                products_recurring,
            )
        return HttpResponseRedirect(reverse_lazy("shop:order-list"))


class ShopView(TemplateView):
    template_name = "shop/shop.html"
    production_day = None

    def get_template_names(self) -> List[str]:
        if self.kwargs.get("production_day", None):
            return ["shop/production_day.html"]
        else:
            return super().get_template_names()

    def setup(self, request, *args, **kwargs):
        if kwargs.get("production_day", None):
            try:
                self.production_day = ProductionDay.objects.get(
                    pk=kwargs.get("production_day")
                )
            except ProductionDay.DoesNotExist:
                self.production_day = ProductionDay.get_production_day(request.user)
        else:
            self.production_day = ProductionDay.get_production_day(request.user)

        return super().setup(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = (
            None if self.request.user.is_anonymous else self.request.user.customer
        )
        if self.production_day:
            context["abo_product_days"] = (
                ProductionDayProduct.get_available_abo_product_days(
                    self.production_day, customer
                )
            )
            context["production_day"] = self.production_day
            context["production_day_next"] = (
                self.production_day.get_next_production_day(self.request.user)
            )
            context["production_day_prev"] = (
                self.production_day.get_prev_production_day(self.request.user)
            )
            production_day_products = self.production_day.production_day_products.published().available_to_user(
                self.request.user
            )
            context["production_day_products"] = production_day_products
            current_customer_order = CustomerOrder.objects.filter(
                customer=customer, production_day=self.production_day
            ).first()
            context["current_customer_order"] = current_customer_order
            # TODO this needs to go at one place, code duplication, very bad idea pages/models
            production_day_products = (
                production_day_products.annotate(
                    ordered_quantity=Subquery(
                        CustomerOrderPosition.objects.filter(
                            Q(product=OuterRef("product__pk"))
                            | Q(product__product_template=OuterRef("product__pk")),
                            order__customer=customer,
                            order__production_day=self.production_day,
                        ).values("quantity")
                    )
                )
                .annotate(
                    price=Subquery(
                        CustomerOrderPosition.objects.filter(
                            Q(product=OuterRef("product__pk"))
                            | Q(product__product_template=OuterRef("product__pk")),
                            order__customer=customer,
                            order__production_day=self.production_day,
                        ).values("price_total")
                    )
                )
                .annotate(
                    has_abo=Exists(
                        Subquery(
                            CustomerOrderTemplatePosition.objects.active().filter(
                                order_template__customer=customer,
                                product=OuterRef("product__pk"),
                            )
                        )
                    )
                )
            )
            if current_customer_order:
                production_day_products = production_day_products.annotate(
                    abo_qty=Subquery(
                        CustomerOrderTemplatePosition.objects.active()
                        .filter(
                            Q(orders__product=OuterRef("product__pk"))
                            | Q(
                                orders__product__product_template=OuterRef(
                                    "product__pk"
                                )
                            ),
                            orders__order__pk=current_customer_order.pk,
                            orders__order__customer=customer,
                        )
                        .values("quantity")
                    )
                )
            context["production_day_products"] = production_day_products
        context["show_remaining_products"] = (
            self.request.tenant.clientsetting.show_remaining_products
        )
        context["point_of_sales"] = PointOfSale.objects.all()
        context["production_days"] = ProductionDay.objects.upcoming().exclude(
            id=self.production_day.pk
        )
        context["all_production_days"] = list(
            ProductionDay.objects.published()
            .available_to_user(self.request.user)
            .annotate(
                formatted_date=Func(
                    F("day_of_sale"),
                    Value("dd.MM.yyyy"),
                    function="to_char",
                    output_field=CharField(),
                )
            )
            .values_list("formatted_date", flat=True)
        )
        return context


# class ProductListView(CustomerRequiredMixin, SingleTableView):
#     model = CustomerOrder
#     table_class = CustomerOrderTable


def redirect_to_production_day_view(request):
    if "production_day_date" in request.POST:
        production_day_date = make_aware(
            datetime.strptime(request.POST.get("production_day_date", None), "%d.%m.%Y")
        ).date()
        production_day = ProductionDay.objects.filter(
            day_of_sale=production_day_date
        ).first()
        if production_day:
            return HttpResponseRedirect(
                reverse(
                    "shop:shop-production-day",
                    kwargs={"production_day": production_day.pk},
                )
            )
    return HttpResponseRedirect("/shop/")


@login_required
def production_day_abo_products(request, pk):
    production_day = ProductionDay.objects.get(pk=pk)
    data = ProductionDayProduct.get_available_abo_product_days(
        production_day, request.user.customer
    )
    return JsonResponse(data)
