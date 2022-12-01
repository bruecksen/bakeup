from django import template
from django.template.defaultfilters import floatformat

from bakeup.shop.models import CustomerOrderPosition

register = template.Library()


@register.simple_tag(takes_context=True)
def customer_quantity(context, production_day_product):
    position = CustomerOrderPosition.objects.filter(order__customer=context['request'].user.customer, order__production_day=production_day_product.production_day, product=production_day_product.product).first()
    return position and position.quantity or None
