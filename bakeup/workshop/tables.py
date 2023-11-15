import django_filters
import django_tables2 as tables
from django import forms
from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _
from django_tables2.utils import A

from bakeup.shop.models import (
    Customer,
    CustomerOrder,
    PointOfSale,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.workshop.models import Category, Product, ProductionPlan


class ProductFilter(django_filters.FilterSet):
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        method="category_filter",
        empty_label=_("Select category"),
    )
    search = django_filters.filters.CharFilter(
        method="filter_search", label=_("Search")
    )

    class Meta:
        model = Product
        fields = ("category",)

    def category_filter(self, queryset, name, value):
        return queryset.filter(category__path__startswith=value.path)

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class ProductTable(tables.Table):
    pk = tables.LinkColumn("workshop:product-detail", args=[A("pk")], verbose_name="#")
    name = tables.LinkColumn("workshop:product-detail", args=[A("pk")])
    action = tables.TemplateColumn(
        template_name="tables/product_action_column.html", verbose_name=""
    )

    class Meta:
        model = Product
        fields = ("pk", "name", "description", "category", "is_recurring")


class ProductionPlanTable(tables.Table):
    pk = tables.LinkColumn(
        "workshop:production-plan-detail", args=[A("pk")], verbose_name="#"
    )
    action = tables.TemplateColumn(
        template_name="tables/production_plan_action_column.html", verbose_name=""
    )
    product = tables.TemplateColumn("#{{ record.product.pk }} {{ record.product }}")

    class Meta:
        model = Product
        fields = ("pk", "start_date", "product", "quantity", "duration")


class ProductionDayTable(tables.Table):
    # pk = tables.LinkColumn('workshop:production-day-update', args=[A('pk')], verbose_name='#')
    day_of_sale = tables.LinkColumn(
        "workshop:production-day-detail",
        args=[A("pk")],
        text=lambda record: record.day_of_sale.strftime("%d.%m.%Y"),
    )
    # name = tables.LinkColumn('workshop:product-detail', args=[A('pk')])
    summary = tables.TemplateColumn(
        template_name="tables/production_day_summary_column.html",
        verbose_name=_("Summary"),
        orderable=False,
    )
    action = tables.TemplateColumn(
        template_name="tables/production_day_action_column.html", verbose_name=""
    )

    class Meta:
        model = ProductionDayProduct
        fields = ("day_of_sale",)


class CustomerOrderFilter(django_filters.FilterSet):
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all().order_by(Lower("user__last_name")),
        empty_label=_("Select a customer"),
    )
    production_day = django_filters.ModelChoiceFilter(
        queryset=ProductionDay.objects.all(), empty_label=_("Select a production day")
    )
    point_of_sale = django_filters.ModelChoiceFilter(
        queryset=PointOfSale.objects.all(), empty_label=_("Select a point of sale")
    )
    search = django_filters.filters.CharFilter(method="filter_search", label="Search")

    class Meta:
        model = CustomerOrder
        fields = ("production_day", "point_of_sale", "customer")

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(customer__user__first_name__icontains=value)
            | Q(customer__user__last_name__icontains=value)
            | Q(customer__user__email__icontains=value)
        )


class CustomerOrderTable(tables.Table):
    # order_nr = tables.LinkColumn('workshop:order-update', args=[A('pk')], verbose_name='#', order_by='pk')
    # order_nr = tables.LinkColumn(verbose_name='#', order_by='pk')
    production_day = tables.LinkColumn(
        "workshop:production-day-detail",
        args=[A("production_day.pk")],
        verbose_name=_("Production Day"),
    )
    customer = tables.LinkColumn(
        "workshop:customer-detail", args=[A("customer.pk")], verbose_name=_("Customer")
    )
    email = tables.TemplateColumn(
        "{{ record.customer.user.email }}", verbose_name=_("eMail")
    )
    positions = tables.TemplateColumn(
        template_name="tables/customer_order_positions_column.html",
        verbose_name=_("Positions"),
    )
    price_total = tables.TemplateColumn(
        "{% if record.price_total %}<nobr>{{ record.price_total }} €</nobr>{% endif %}",
        verbose_name=_("Sum"),
    )
    collected = tables.TemplateColumn(
        "{% if record.is_picked_up %}x{% endif %}",
        verbose_name=_("Collected"),
        orderable=False,
    )
    actions = tables.TemplateColumn(
        template_name="tables/customer_order_actions_column.html",
        verbose_name="",
        exclude_from_export=True,
    )
    note = tables.TemplateColumn(
        "{{ record.notes.first.content|default:'' }}",
        verbose_name=_("Note"),
    )

    class Meta:
        model = CustomerOrder
        order_by = "production_day"
        fields = (
            "production_day",
            "customer",
            "email",
            "point_of_sale",
            "positions",
            "price_total",
            "note",
        )

    def value_positions(self, value):
        return "\n".join(
            [
                "{}x {}{}".format(
                    position.quantity,
                    position.product,
                    " {}".format(position.price_total) or "",
                )
                for position in value.all()
            ]
        )


class ProductionDayExportTable(tables.Table):
    last_name = tables.TemplateColumn(
        "{{ record.customer.user.last_name }}", verbose_name=_("Last Name")
    )
    first_name = tables.TemplateColumn(
        "{{ record.customer.user.first_name }}", verbose_name=_("First Name")
    )
    email = tables.TemplateColumn(
        "{{ record.customer.user.email }}", verbose_name=_("eMail")
    )
    phone = tables.TemplateColumn(
        "{{ record.customer.telephone_number|default:'' }}", verbose_name=_("phone")
    )

    class Meta:
        model = CustomerOrder
        fields = ()


class GroupTable(tables.Table):
    token = tables.TemplateColumn(
        "{% load workshop_tags %}{% token_url record.token %}",
        verbose_name=_("Signup url"),
    )
    user_count = tables.Column(empty_values=(), verbose_name=_("Users"))
    actions = tables.TemplateColumn(
        template_name="tables/group_actions_column.html", verbose_name=""
    )

    class Meta:
        model = Group
        fields = ("name", "token")

    def render_user_count(self, value, record):
        return record.user_set.count()


class CustomerTable(tables.Table):
    email = tables.LinkColumn(
        "workshop:customer-detail",
        args=[A("pk")],
        text=lambda record: record.user.email,
        verbose_name=_("eMail"),
    )
    abos = tables.TemplateColumn(
        template_name="tables/customer_abos_column.html",
        verbose_name="Abos",
        exclude_from_export=True,
    )
    actions = tables.TemplateColumn(
        template_name="tables/customer_actions_column.html",
        verbose_name="",
        exclude_from_export=True,
    )
    street = tables.Column(visible=False)
    postal_code = tables.Column(visible=False)
    city = tables.Column(visible=False)
    telephone_number = tables.Column(visible=False)

    class Meta:
        model = Customer
        fields = (
            "email",
            "user__first_name",
            "user__last_name",
            "user__date_joined",
            "user__is_active",
            "point_of_sale",
            "abos",
        )

    def value_street(self, record):
        return "{} {}".format(record.street, record.street_number)


class CustomerFilter(django_filters.FilterSet):
    abos = django_filters.ModelChoiceFilter(
        method="filter_abos",
        queryset=Product.objects.filter(
            category__name__iexact=settings.META_PRODUCT_CATEGORY_NAME
        ),
        empty_label="Select abo",
    )
    point_of_sale = django_filters.ModelChoiceFilter(
        queryset=PointOfSale.objects.all(), empty_label=_("Select a point of sale")
    )
    search = django_filters.filters.CharFilter(method="filter_search", label="Search")
    group = django_filters.ModelChoiceFilter(
        method="filter_group",
        queryset=Group.objects.all(),
        empty_label=_("Select a group"),
    )

    class Meta:
        model = Customer
        fields = ("point_of_sale",)

    def filter_abos(self, queryset, name, value):
        return queryset.filter(order_templates__product=value)

    def filter_group(self, queryset, name, value):
        return queryset.filter(user__groups=value)

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(user__email__icontains=value)
        )


class ProductionPlanFilter(django_filters.FilterSet):
    state = django_filters.MultipleChoiceFilter(
        choices=ProductionPlan.State.choices, widget=forms.CheckboxSelectMultiple
    )
    production_day = django_filters.ModelChoiceFilter(
        queryset=ProductionDay.objects.all(), empty_label=_("Select a production day")
    )

    class Meta:
        model = ProductionPlan
        fields = ("production_day",)


class PointOfSaleTable(tables.Table):
    name = tables.LinkColumn("workshop:point-of-sale-update", args=[A("pk")])
    customers = tables.TemplateColumn(
        "{{ record.get_customer_count }}", verbose_name="Customers"
    )
    actions = tables.TemplateColumn(
        template_name="tables/point_of_sale_actions_column.html",
        verbose_name="",
        exclude_from_export=True,
    )

    class Meta:
        model = PointOfSale
        order_by = "production_day"
        fields = ("name", "short_name", "is_primary", "customers", "actions")
