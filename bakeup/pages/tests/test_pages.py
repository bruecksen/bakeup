import json
from decimal import Decimal

import pytest
from bs4 import BeautifulSoup

from bakeup.pages.models import PointOfSalePage
from bakeup.pages.tests.factories import (
    BlockReferencePageFactory,
    ContentPageFactory,
    PointOfSalePageFactory,
)
from bakeup.shop.tests.factories import PointOfSaleFactory
from bakeup.users.tests.factories import UserFactory

INTRO = {
    "type": "text",
    "value": {"text": "<p>Alle Bausteine</p>", "alignment": "start"},
}


@pytest.fixture
def block_reference_page(shop_page):
    return BlockReferencePageFactory(
        parent=shop_page, title="Bausteine", content=[INTRO]
    )


def test_anonymous_visitor_gets_404_for_block_reference_page(
    client, block_reference_page
):
    response = client.get(block_reference_page.url)

    assert response.status_code == 404


def test_customer_gets_404_for_block_reference_page(client, block_reference_page):
    client.force_login(UserFactory(is_staff=False))

    response = client.get(block_reference_page.url)

    assert response.status_code == 404


def test_staff_user_sees_block_reference_page_with_visibility_note(
    client, block_reference_page
):
    client.force_login(UserFactory(is_staff=True))

    response = client.get(block_reference_page.url)

    assert response.status_code == 200
    html = response.content.decode()
    assert "<p>Alle Bausteine</p>" in html
    assert "Diese Seite ist nur für Bäcker:innen sichtbar." in html


def test_anonymous_visitor_sees_content_page(client, shop_page):
    page = ContentPageFactory(parent=shop_page, title="Über uns", content=[INTRO])

    response = client.get(page.url)

    assert response.status_code == 200
    assert "<p>Alle Bausteine</p>" in response.content.decode()


def test_block_reference_page_is_left_out_of_the_sitemap(block_reference_page):
    assert block_reference_page.get_sitemap_urls() == []


@pytest.fixture
def point_of_sale_page(shop_page):
    return PointOfSalePageFactory(
        parent=shop_page, title="Abholstellen", content=[INTRO]
    )


def cards(response):
    html = BeautifulSoup(response.content, "html.parser")
    return [
        {
            "name": card.select_one(".card-title").get_text(strip=True),
            "details": [
                element.get_text(" ", strip=True)
                for element in card.select(
                    ".pos-address, .pos-pickup-times, .pos-description"
                )
            ],
        }
        for card in html.select(".pos-card")
    ]


def test_point_of_sale_page_lists_public_points_of_sale_with_their_details(
    client, point_of_sale_page
):
    PointOfSaleFactory(
        name="Hofladen <Müller & Söhne>",
        street="Große Fleischergasse",
        street_number="12a",
        postal_code="04109",
        city="Leipzig",
        pickup_times=[(4, "16:00", "18:00"), (5, "09:00", "12:00")],
        description="Eingang über den Hof.",
    )
    PointOfSaleFactory(name="Markt")
    PointOfSaleFactory(name="Lieferung Café", is_internal=True, city="Halle")

    response = client.get(point_of_sale_page.url)

    assert response.status_code == 200
    assert "<p>Alle Bausteine</p>" in response.content.decode()
    assert cards(response) == [
        {
            "name": "Hofladen <Müller & Söhne>",
            "details": [
                "Große Fleischergasse 12a 04109 Leipzig",
                "Freitag, 16:00–18:00 Uhr Samstag, 09:00–12:00 Uhr",
                "Eingang über den Hof.",
            ],
        },
        {"name": "Markt", "details": []},
    ]


def test_point_of_sale_page_shows_map_with_the_pinned_points_of_sale(
    client, point_of_sale_page, settings
):
    settings.SMARTMAPS_API_KEY = "test-key"
    pinned = PointOfSaleFactory(
        name="Hofladen",
        street="Hauptstraße",
        street_number="5",
        pickup_times=[(4, "14:00", "19:00")],
        latitude=Decimal("51.339700"),
        longitude=Decimal("12.373100"),
    )
    PointOfSaleFactory(name="Markt")
    PointOfSaleFactory(
        name="Lieferung Café",
        is_internal=True,
        latitude=Decimal("51.5"),
        longitude=Decimal("12.5"),
    )

    response = client.get(point_of_sale_page.url)

    html = BeautifulSoup(response.content, "html.parser")
    [map_element] = html.select("[data-pos-map]")
    assert map_element["data-style-url"] == (
        "https://tiles.smartmaps.cloud/styles/v1/smartmaps/light/style.json"
        "?apiKey=test-key"
    )
    markers = html.find("script", id=map_element["data-markers"])
    assert json.loads(markers.string) == [
        {
            "id": pinned.pk,
            "name": "Hofladen",
            "address": "Hauptstraße 5",
            "pickup_times": ["Freitag, 14:00–19:00 Uhr"],
            "lat": 51.3397,
            "lng": 12.3731,
        }
    ]
    assert [button["data-pos-focus"] for button in html.select("[data-pos-focus]")] == [
        str(pinned.pk)
    ]


@pytest.mark.parametrize(
    "api_key, coordinates",
    [
        ("", {"latitude": Decimal("51.339700"), "longitude": Decimal("12.373100")}),
        ("test-key", {}),
    ],
    ids=["no key", "no pinned point of sale"],
)
def test_point_of_sale_page_has_no_map_markup(
    client, point_of_sale_page, settings, api_key, coordinates
):
    settings.SMARTMAPS_API_KEY = api_key
    PointOfSaleFactory(name="Hofladen", **coordinates)

    response = client.get(point_of_sale_page.url)

    html = BeautifulSoup(response.content, "html.parser")
    assert [card["name"] for card in cards(response)] == ["Hofladen"]
    assert html.select("[data-pos-map], [data-pos-focus], script[src*=pos_map]") == []
    assert "maplibre" not in response.content.decode()


def test_second_point_of_sale_page_cannot_be_created(point_of_sale_page, shop_page):
    assert PointOfSalePage.can_create_at(shop_page) is False


@pytest.mark.parametrize(
    "display, map_count, names",
    [
        ("map_and_list", 1, ["Hofladen"]),
        ("map", 1, []),
        ("list", 0, ["Hofladen"]),
    ],
)
def test_point_of_sale_page_shows_map_and_list_as_chosen(
    client, point_of_sale_page, settings, display, map_count, names
):
    settings.SMARTMAPS_API_KEY = "test-key"
    PointOfSaleFactory(
        name="Hofladen", latitude=Decimal("51.339700"), longitude=Decimal("12.373100")
    )
    point_of_sale_page.display = display
    point_of_sale_page.save()

    response = client.get(point_of_sale_page.url)

    html = BeautifulSoup(response.content, "html.parser")
    assert len(html.select("[data-pos-map]")) == map_count
    assert [card["name"] for card in cards(response)] == names


POINTS_OF_SALE_BLOCK = ("points_of_sale", {"heading": "Unsere Abholstellen"})


@pytest.mark.parametrize(
    "content",
    [
        [POINTS_OF_SALE_BLOCK],
        [("column11", {"left": [POINTS_OF_SALE_BLOCK], "right": []})],
        [("section", {"content": [POINTS_OF_SALE_BLOCK]})],
    ],
    ids=["top level", "in a column", "in a section"],
)
def test_points_of_sale_block_on_the_page_replaces_the_automatic_list(
    client, shop_page, content
):
    PointOfSaleFactory(name="Hofladen")
    page = PointOfSalePageFactory(parent=shop_page, title="Abholen", content=content)

    response = client.get(page.url)

    # Once from the block, not a second time from the page itself.
    assert [card["name"] for card in cards(response)] == ["Hofladen"]
