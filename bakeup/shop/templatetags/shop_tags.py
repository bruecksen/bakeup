from django import template
from django.template.defaultfilters import floatformat

from bakeup.shop.models import CustomerOrderPosition, ProductionDayProduct, PointOfSale

register = template.Library()


@register.simple_tag(takes_context=True)
def customer_quantity(context, production_day_product):
    position = CustomerOrderPosition.objects.filter(order__customer=context['request'].user.customer, order__production_day=production_day_product.production_day, product=production_day_product.product).first()
    return position and position.quantity or None

@register.simple_tag(takes_context=True)
def max_quantity(context, production_day, product):
    production_day_product = ProductionDayProduct.objects.get(production_day=production_day, product=product)
    return production_day_product.calculate_max_quantity(context['request'].user.customer)

@register.filter(name='times') 
def times(number):
    return range(number + 1)