import django_tables2 as tables
from django_tables2.utils import A
from django.utils.translation import gettext_lazy as _

from bakeup.shop.models import CustomerOrder


class CustomerOrderTable(tables.Table):
    order_nr = tables.Column(verbose_name='#', order_by='pk')
    production_day = tables.Column(verbose_name=_('Productionday'))
    point_of_sale = tables.Column(verbose_name=_('Point of Sale'))
    positions = tables.TemplateColumn(template_name='tables/customer_order_positions_column.html', verbose_name=_('Positions'))

    class Meta:
        model = CustomerOrder
        fields = ("order_nr", "production_day", "point_of_sale")