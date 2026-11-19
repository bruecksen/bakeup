from django import template
from django.db.models import Q
from django.template.defaultfilters import floatformat

from bakeup.pages.models import GeneralSettings
from bakeup.shop.maps import (
    AUTOCOMPLETE_URL,
    get_autocomplete_token_url,
    get_geocode_url,
    get_map_style_url,
)
from bakeup.shop.models import CustomerOrderPosition, ProductionDayProduct

register = template.Library()

register.simple_tag(get_map_style_url, name="map_style_url")
register.simple_tag(get_geocode_url, name="map_geocode_url")
register.simple_tag(get_autocomplete_token_url, name="map_autocomplete_token_url")


@register.filter
def have_summary(points_of_sale):
    """Whether any point of sale has pick-up times or an address to show."""
    return any(point_of_sale.summary_for() for point_of_sale in points_of_sale)


@register.filter
def pickup_times_text(point_of_sale, production_day=None):
    return " · ".join(
        str(pickup_time)
        for pickup_time in point_of_sale.pickup_times_for(production_day or None)
    )


@register.filter
def pickup_times_for(point_of_sale, production_day=None):
    return point_of_sale.pickup_times_for(production_day)


@register.simple_tag
def map_autocomplete_url():
    return AUTOCOMPLETE_URL


@register.simple_tag(takes_context=True)
def base_price(context, product):
    if not product.weight or not product.sale_price:
        return ""
    return f"{product.sale_price.price / (product.weight_in_base_unit / 1000)} / 1 kg"


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


@register.filter(name="clever_weight")
def clever_weight(weight):
    if not weight:
        return ""
    if weight >= 1000:
        return f"{floatformat(weight / 1000)} kg"
        # return f"{formats.localize(Decimal(round(weight / 1000, 1)).normalize(), use_l10n=True)}kg"
    else:
        return f"{weight:.0f} g"
