import django_tables2 as tables
from django_tables2.utils import A

from bakeup.workshop.models import Product


class ProductTable(tables.Table):
    pk = tables.LinkColumn('workshop:product-detail', args=[A('pk')], verbose_name='#')
    name = tables.LinkColumn('workshop:product-detail', args=[A('pk')])
    action = tables.TemplateColumn(template_name="tables/product_action_column.html", verbose_name="")

    class Meta:
        model = Product
        fields = ("pk", "name", "description", "categories", "is_sellable", "is_buyable", "is_composable")


class ProductionPlanTable(tables.Table):
    action = tables.TemplateColumn(template_name="tables/product_action_column.html", verbose_name="")

    class Meta:
        model = Product
        fields = ("pk", "parent_plan", "start_date", "product", "quantity", "duration")
