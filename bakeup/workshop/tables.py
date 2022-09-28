from django.db.models import Q

import django_tables2 as tables
import django_filters
from django_tables2.utils import A

from bakeup.workshop.models import Category, Product
from bakeup.shop.models import CustomerOrder, PointOfSale, ProductionDay, ProductionDayProduct


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
        fields = ("pk", "name", "description", "category", "is_sellable", "is_buyable", "is_composable")


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
    production_day = django_filters.ModelChoiceFilter(queryset=ProductionDay.objects.all(), empty_label='Select a production day')
    point_of_sale = django_filters.ModelChoiceFilter(queryset=PointOfSale.objects.all(), empty_label='Select a point of sale')
    
    class Meta:
        model = CustomerOrder
        fields = ('production_day','point_of_sale')


class CustomerOrderTable(tables.Table):
    order_nr = tables.Column(verbose_name='#', order_by='pk')
    production_day = tables.LinkColumn('workshop:production-day-detail', args=[A('production_day.pk')])
    customer = tables.TemplateColumn("{{ record.customer }}")
    positions = tables.TemplateColumn(template_name='tables/customer_order_positions_column.html', verbose_name='Positions')
    actions = tables.TemplateColumn(template_name='tables/customer_order_actions_column.html', verbose_name='')

    class Meta:
        model = CustomerOrder
        fields = ("order_nr", "production_day", "customer", "point_of_sale")