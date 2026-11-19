import uuid
from urllib.parse import quote, unquote

from django.conf import settings

from bakeup.shop.models import PointOfSale

API_KEY_PLACEHOLDER = "{api_key}"


def get_map_style_url():
    """The style URL for MapLibre, empty when no map can be shown."""
    style_url = settings.MAP_STYLE_URL or ""
    if API_KEY_PLACEHOLDER not in style_url:
        return style_url
    if not settings.SMARTMAPS_API_KEY:
        return ""
    return style_url.replace(API_KEY_PLACEHOLDER, settings.SMARTMAPS_API_KEY)


GEOCODE_URL = "https://www.yellowmap.de/api_rst/v2/geojson/geocode"


def get_geocode_url():
    """
    The SmartMaps geocoding endpoint the workshop calls from the browser to find
    an address and to name the place of a pin. Empty without a key.
    """
    if not settings.SMARTMAPS_API_KEY:
        return ""
    # The account shows some keys already URL-encoded.
    return f"{GEOCODE_URL}?apiKey={quote(unquote(settings.SMARTMAPS_API_KEY), safe='')}"


AUTOCOMPLETE_TOKEN_URL = "https://www.yellowmap.de/api_rst/api/autocompleteToken"
AUTOCOMPLETE_URL = "https://autocomplete.smartmaps.cloud/api/v5/Autocomplete"


def get_autocomplete_token_url():
    """
    Where the browser gets the short-lived token for the type-ahead of the
    address search (AUTOCOMPLETE_URL). Empty without a key.
    """
    if not settings.SMARTMAPS_API_KEY:
        return ""
    key = quote(unquote(settings.SMARTMAPS_API_KEY), safe="")
    return f"{AUTOCOMPLETE_TOKEN_URL}?apiKey={key}"


def get_point_of_sale_overview_context(show_map=True, show_list=True):
    """
    Context of shop/includes/point_of_sale_overview.html, shared by the
    point of sale page and the points of sale block. The map only appears with
    a configured style and at least one point of sale that has a pin. Without
    a map the list is always shown, so the overview is never empty.
    """
    points_of_sale = list(
        PointOfSale.objects.public().prefetch_related("pickup_times").order_by("name")
    )
    map_style_url = get_map_style_url() if show_map else ""
    markers = []
    if map_style_url:
        markers = [
            {
                "id": point_of_sale.pk,
                "name": point_of_sale.name,
                "address": point_of_sale.address_line,
                "pickup_times": [
                    str(pickup_time) for pickup_time in point_of_sale.pickup_times_for()
                ],
                "lat": float(point_of_sale.latitude),
                "lng": float(point_of_sale.longitude),
            }
            for point_of_sale in points_of_sale
            if point_of_sale.has_location
        ]
    # Several overviews can be on one page, each needs its own DOM ids.
    overview_id = uuid.uuid4().hex
    map_style_url = map_style_url if markers else ""
    return {
        "points_of_sale": points_of_sale,
        "show_list": show_list or not map_style_url,
        "map_style_url": map_style_url,
        "map_markers": markers,
        "map_id": f"pos-map-{overview_id}",
        "map_markers_id": f"pos-markers-{overview_id}",
    }
