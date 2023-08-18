from django.db.models import Q
from django import forms
import django_tables2 as tables
import django_filters
from django_tables2.utils import A
from django.conf import settings

from bakeup.workshop.models import Category, Product, ProductionPlan
from bakeup.shop.models import CustomerOrder, PointOfSale, ProductionDay, ProductionDayProduct, Customer


class ProductFilter(django_filters.FilterSet):
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.all(), method='category_filter', empty_label='Select category')
    search = django_filters.filters.CharFilter(method='filter_search', label="Search")

    class Meta:
        model = Product
        fields = ('category',)

    def category_filter(self, queryset, name, value):
        return queryset.filter(category__path__startswith=value.path)

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

class ProductTable(tables.Table):
    pk = tables.LinkColumn('workshop:product-detail', args=[A('pk')], verbose_name='#')
    name = tables.LinkColumn('workshop:product-detail', args=[A('pk')])
    action = tables.TemplateColumn(template_name="tables/product_action_column.html", verbose_name="")

    class Meta:
        model = Product
        fields = ("pk", "name", "description", "category", "is_recurring")


class ProductionPlanTable(tables.Table):
    pk = tables.LinkColumn('workshop:production-plan-detail', args=[A('pk')], verbose_name='#')
    action = tables.TemplateColumn(template_name="tables/production_plan_action_column.html", verbose_name="")
    product = tables.TemplateColumn("#{{ record.product.pk }} {{ record.product }}")

    class Meta:
        model = Product
        fields = ("pk", "start_date", "product", "quantity", "duration")




class ProductionDayTable(tables.Table):
    # pk = tables.LinkColumn('workshop:production-day-update', args=[A('pk')], verbose_name='#')
    day_of_sale = tables.LinkColumn('workshop:production-day-detail', args=[A('pk')], text=lambda record: record.day_of_sale.strftime('%d.%m.%Y'))
    # name = tables.LinkColumn('workshop:product-detail', args=[A('pk')])
    summary = tables.TemplateColumn(template_name="tables/production_day_summary_column.html", verbose_name="Summary", orderable=False)
    action = tables.TemplateColumn(template_name="tables/production_day_action_column.html", verbose_name="")

    class Meta:
        model = ProductionDayProduct
        fields = ("day_of_sale", )


class CustomerOrderFilter(django_filters.FilterSet):
    customer = django_filters.ModelChoiceFilter(queryset=Customer.objects.all(), empty_label='Select a customer')
    production_day = django_filters.ModelChoiceFilter(queryset=ProductionDay.objects.all(), empty_label='Select a production day')
    point_of_sale = django_filters.ModelChoiceFilter(queryset=PointOfSale.objects.all(), empty_label='Select a point of sale')
    
    class Meta:
        model = CustomerOrder
        fields = ('production_day','point_of_sale', 'customer')


class CustomerOrderTable(tables.Table):
    # order_nr = tables.LinkColumn('workshop:order-update', args=[A('pk')], verbose_name='#', order_by='pk')
    # order_nr = tables.LinkColumn(verbose_name='#', order_by='pk')
    production_day = tables.LinkColumn('workshop:production-day-detail', args=[A('production_day.pk')])
    customer = tables.LinkColumn('workshop:customer-detail', args=[A("customer.pk")])
    email = tables.TemplateColumn("{{ record.customer.user.email }}")
    positions = tables.TemplateColumn(template_name='tables/customer_order_positions_column.html', verbose_name='Positions')
    price_total = tables.TemplateColumn("{% if record.price_total %}<nobr>{{ record.price_total }} €</nobr>{% endif %}", verbose_name='Betrag')
    collected = tables.TemplateColumn('{% if record.is_picked_up %}x{% endif %}', verbose_name='Collected', orderable=False)
    actions = tables.TemplateColumn(template_name='tables/customer_order_actions_column.html', verbose_name='', exclude_from_export=True)

    class Meta:
        model = CustomerOrder
        order_by = 'production_day'
        fields = ("production_day", "customer", "email", "point_of_sale", "positions", "price_total")

    def value_positions(self, value):
        return "\n".join(["{}x {}{}".format(position.quantity, position.product, " {}".format(position.price_total) or '') for position in value.all()])



class ProductionDayExportTable(tables.Table):
    last_name = tables.TemplateColumn('{{ record.customer.user.last_name }}', verbose_name='Nachname')
    first_name = tables.TemplateColumn('{{ record.customer.user.first_name }}', verbose_name='Vorname')
    email = tables.TemplateColumn("{{ record.customer.user.email }}", verbose_name='E-Mail')
    phone = tables.TemplateColumn("{{ record.customer.telephone_number|default:'' }}", verbose_name='Telefonnummer')

    class Meta:
        model = CustomerOrder
        fields = ()


class CustomerTable(tables.Table):
    # planned = tables.TemplateColumn('{% if record.is_planned %}<i class="fa-regular fa-circle-check"></i>{% else %}<i class="far fa-times-circle"></i>{% endif %}', orderable=False, verbose_name='')
    # order_nr = tables.Column(verbose_name='#', order_by='pk')
    # production_day = tables.LinkColumn('workshop:production-day-detail', args=[A('production_day.pk')])
    # customer = tables.TemplateColumn("{{ record.customer }}")
    email = tables.LinkColumn('workshop:customer-detail', args=[A('pk')], text=lambda record: record.user.email, verbose_name='E-Mail')
    abos = tables.TemplateColumn(template_name='tables/customer_abos_column.html', verbose_name='Abos', exclude_from_export=True)
    actions = tables.TemplateColumn(template_name='tables/customer_actions_column.html', verbose_name='', exclude_from_export=True)
    street = tables.Column(visible=False)
    postal_code = tables.Column(visible=False)
    city = tables.Column(visible=False)
    telephone_number = tables.Column(visible=False)

    class Meta:
        model = Customer
        fields = ("email", "user__first_name", "user__last_name", "user__date_joined", "point_of_sale", "abos")

    def value_street(self, record):
        return "{} {}".format(record.street, record.street_number)


class CustomerFilter(django_filters.FilterSet):
    abos = django_filters.ModelChoiceFilter(method='filter_abos', queryset=Product.objects.filter(category__name__iexact=settings.META_PRODUCT_CATEGORY_NAME), empty_label='Select abo')
    point_of_sale = django_filters.ModelChoiceFilter(queryset=PointOfSale.objects.all(), empty_label='Select a point of sale')
    search = django_filters.filters.CharFilter(method='filter_search', label="Search")
    
    class Meta:
        model = Customer
        fields = ('point_of_sale', )

    def filter_abos(self, queryset, name, value):
        return queryset.filter(order_templates__product=value)

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(user__first_name__icontains=value) | Q(user__last_name__icontains=value)| Q(user__email__icontains=value))



class ProductionPlanFilter(django_filters.FilterSet):
    state = django_filters.MultipleChoiceFilter(choices=ProductionPlan.State.choices, widget=forms.CheckboxSelectMultiple)
    production_day = django_filters.ModelChoiceFilter(queryset=ProductionDay.objects.all(), empty_label='Select a production day')
    
    class Meta:
        model = ProductionPlan
        fields = ('production_day', )


class PointOfSaleTable(tables.Table):
    name = tables.LinkColumn('workshop:point-of-sale-update', args=[A('pk')])
    customers = tables.TemplateColumn('{{ record.get_customer_count }}', verbose_name='Customers')
    actions = tables.TemplateColumn(template_name='tables/point_of_sale_actions_column.html', verbose_name='', exclude_from_export=True)

    class Meta:
        model = PointOfSale
        order_by = 'production_day'
        fields = ("name", "short_name", "is_primary", "customers", "actions")