import django_tables2 as tables
import django_filters
from django_tables2.utils import A

from bakeup.workshop.models import Category, Product
from bakeup.shop.models import ProductionDayProduct


class ProductFilter(django_filters.FilterSet):
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.all(), method='category_filter')

    class Meta:
        model = Product
        fields = ('category',)

    def category_filter(self, queryset, name, value):
        return queryset.filter(category__path__startswith=value.path)

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
    day_of_sale = tables.DateColumn(format ='d.m.Y')
    # name = tables.LinkColumn('workshop:product-detail', args=[A('pk')])
    products = tables.TemplateColumn(template_name="tables/production_day_products_column.html", verbose_name="Products")
    action = tables.TemplateColumn(template_name="tables/production_day_action_column.html", verbose_name="")

    class Meta:
        model = ProductionDayProduct
        fields = ("day_of_sale", )