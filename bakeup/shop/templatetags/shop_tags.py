from django import template
from django.db.models import Q

from bakeup.pages.models import GeneralSettings
from bakeup.shop.models import CustomerOrderPosition, ProductionDayProduct

register = template.Library()


@register.simple_tag(takes_context=True)
def customer_quantity(context, production_day_product):
    position = CustomerOrderPosition.objects.filter(
        Q(product=production_day_product.product)
        | Q(product__product_template=production_day_product.product),
        order__customer=context["request"].user.customer,
        order__production_day=production_day_product.production_day,
    ).first()
    return position and position.quantity or None


@register.simple_tag(takes_context=True)
def upcoming_available_production_days(context, product):
    user = context["request"].user
    if user.is_authenticated:
        return product.production_days.published().upcoming().available_to_user(user)
    else:
        return product.production_days.published().upcoming().available()


@register.simple_tag(takes_context=True)
def available_products(context, production_day):
    user = context["request"].user
    general_settings = GeneralSettings.load(request_or_site=context["request"])
    ordering = general_settings.production_day_product_ordering
    if user.is_authenticated:
        qs = (
            production_day.production_day_products.published()
            .upcoming()
            .available_to_user(user)
        )
    else:
        qs = production_day.production_day_products.published().upcoming().available()
    return qs.order_by(ordering)


@register.simple_tag(takes_context=True)
def max_quantity(context, production_day, product):
    production_day_product = ProductionDayProduct.objects.get(
        production_day=production_day, product=product
    )
    return production_day_product.calculate_max_quantity(
        context["request"].user.customer
    )


@register.filter(name="times")
def times(number):
    return range(number + 1)
