from django import template

register = template.Library()


@register.simple_tag
def baker_percentage(weight, flour_weight):
    return "{:.0f}%".format(weight / flour_weight * 100)