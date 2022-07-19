from django import template
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
    if float(value) < 100:
        return floatformat(round(value, 1), -1)
    else:
        return floatformat(round(value), 0)

