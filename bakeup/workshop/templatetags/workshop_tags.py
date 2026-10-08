from decimal import Decimal

from django import template
from django.db.models import Q
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils import formats

register = template.Library()


@register.simple_tag(takes_context=True)
def workshop_section(context):
    # The sidebar entry a workshop page belongs to: the first segment of its
    # URL, e.g. "orders" for /workshop/orders/5/update/. Product pages belong
    # to the product range when the product is sold. The user pages are the
    # profile.
    request = context["request"]
    match = request.resolver_match
    if match and match.namespace == "users":
        return "profile"
    if not match or match.namespace != "workshop":
        return ""
    path = request.path.removeprefix(reverse("workshop:workshop"))
    section = path.split("/", 1)[0] or "dashboard"
    if section == "products":
        product = context.get("object")
        if getattr(product, "is_sellable", False) or "sellable" in request.GET:
            return "recipes"
    return section


@register.simple_tag
def baker_percentage(weight, flour_weight):
    if flour_weight:
        value = weight / flour_weight * 100
        value = clever_rounding(value)
        return "{}%".format(value)


@register.simple_tag
def baker_ratio(weight, flour_weight):
    if flour_weight:
        return clever_rounding(weight / flour_weight * 100)
    return ""


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


@register.filter
def model_label(obj):
    return obj._meta.label_lower


LARGER_UNITS = {"g": "kg", "ml": "l"}
# Bakers weigh in grams, scales show grams up to about 10 kg.
LARGER_UNIT_FROM = 10000


@register.filter
def clever_unit(value, unit="g"):
    # Large amounts in the larger unit, without losing a gram: 80760 g is
    # 80,76 kg. Below as clever_rounding does, 1250 g stays 1250 g.
    if value is None or value == "":
        return ""
    unit = unit or "g"
    if unit in LARGER_UNITS and abs(round(value)) >= LARGER_UNIT_FROM:
        amount = (Decimal(round(value)) / 1000).normalize()
        # normalize() writes 2000 as 2E+3.
        amount = (
            amount.quantize(Decimal(1)) if amount == amount.to_integral() else amount
        )
        return (
            f"{formats.number_format(amount, use_l10n=True)}\u00a0{LARGER_UNITS[unit]}"
        )
    return f"{clever_rounding(value)}\u00a0{unit}"
