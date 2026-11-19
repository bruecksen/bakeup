from django import template

from bakeup.pages.models import PointOfSalePage

register = template.Library()


@register.simple_tag(takes_context=True)
def point_of_sale_page_url(context):
    """URL of the live point of sale page, empty when there is none."""
    request = context.get("request")
    # The summary of a point of sale is rendered once per checkout modal, the
    # order list has one modal per order.
    if request is not None and hasattr(request, "_point_of_sale_page_url"):
        return request._point_of_sale_page_url
    page = PointOfSalePage.objects.live().first()
    url = (page.get_url(request) or "") if page else ""
    if request is not None:
        request._point_of_sale_page_url = url
    return url
