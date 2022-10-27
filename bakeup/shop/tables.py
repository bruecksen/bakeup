import django_tables2 as tables
from django_tables2.utils import A

from bakeup.shop.models import CustomerOrder


class CustomerOrderTable(tables.Table):
    order_nr = tables.Column(verbose_name='#', order_by='pk')
    # production_day = tables.LinkColumn('workshop:production-day-detail', args=[A('production_day.pk')])
    positions = tables.TemplateColumn(template_name='tables/customer_order_positions_column.html', verbose_name='Positions')

    class Meta:
        model = CustomerOrder
        fields = ("order_nr", "production_day", "point_of_sale")