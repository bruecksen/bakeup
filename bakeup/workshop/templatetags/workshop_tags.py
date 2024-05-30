from django import template
from django.db.models import Q
from django.template.defaultfilters import floatformat

register = template.Library()


@register.simple_tag
def baker_percentage(weight, flour_weight):
    if flour_weight:
        value = weight / flour_weight * 100
        value = clever_rounding(value)
        return "{}%".format(value)


@register.filter
def clever_rounding(value):
    if value is None:
        return None
    if float(value) < 100:
        return floatformat(round(value, 1), -1)
    else:
        return floatformat(round(value), 0)


@register.simple_tag
def ordered_quantity(order, product):
    position = order.positions.filter(
        Q(product=product) | Q(product__product_template=product),
    ).first()
    return position and position.quantity or 0


@register.simple_tag(takes_context=True)
def token_url(context, token):
    if token:
        return token.token_url(context.get("request"))
