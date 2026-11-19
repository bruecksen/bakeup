from datetime import date
from decimal import Decimal

import pytest

from bakeup.shop.models import PointOfSale
from bakeup.shop.tests.factories import PointOfSaleFactory, ProductionDayFactory


@pytest.mark.parametrize(
    "address, lines, line",
    [
        ({}, [], ""),
        (
            {"street": None, "street_number": None, "postal_code": None, "city": None},
            [],
            "",
        ),
        ({"street": "Hauptstraße"}, ["Hauptstraße"], "Hauptstraße"),
        ({"street_number": "5a"}, ["5a"], "5a"),
        ({"city": "Leipzig"}, ["Leipzig"], "Leipzig"),
        (
            {"street": "Hauptstraße", "street_number": "5a", "postal_code": "04109"},
            ["Hauptstraße 5a", "04109"],
            "Hauptstraße 5a, 04109",
        ),
        (
            {
                "street": "Große Fleischergasse",
                "street_number": "12",
                "postal_code": "04109",
                "city": "Leipzig-Südvorstadt",
            },
            ["Große Fleischergasse 12", "04109 Leipzig-Südvorstadt"],
            "Große Fleischergasse 12, 04109 Leipzig-Südvorstadt",
        ),
    ],
)
def test_address_is_built_from_the_fields_that_are_set(address, lines, line):
    point_of_sale = PointOfSale(name="Laden", **address)

    assert point_of_sale.address_lines == lines
    assert point_of_sale.address_line == line


@pytest.mark.parametrize(
    "latitude, longitude, has_location",
    [
        (None, None, False),
        (Decimal("51.339700"), None, False),
        (None, Decimal("12.373100"), False),
        (Decimal("51.339700"), Decimal("12.373100"), True),
        (Decimal("0"), Decimal("0"), True),
    ],
)
def test_point_of_sale_has_location_with_both_coordinates(
    latitude, longitude, has_location
):
    point_of_sale = PointOfSale(name="Laden", latitude=latitude, longitude=longitude)

    assert point_of_sale.has_location is has_location


def test_public_points_of_sale_exclude_internal_ones(tenant_db):
    PointOfSaleFactory(name="Laden")
    PointOfSaleFactory(name="Lieferung Café", is_internal=True)
    PointOfSaleFactory(name="Markt")

    assert list(
        PointOfSale.objects.public().order_by("name").values_list("name", flat=True)
    ) == ["Laden", "Markt"]


@pytest.mark.parametrize(
    "day_of_sale, pickup_times",
    [
        # A Friday: only the pick-up time of that weekday.
        (date(2026, 11, 20), ["Freitag, 14:00–19:00 Uhr"]),
        # A Wednesday has no pick-up time, the pick-up is on a later day.
        (
            date(2026, 11, 18),
            ["Dienstag, 09:30–12:00 Uhr", "Freitag, 14:00–19:00 Uhr"],
        ),
    ],
)
def test_pickup_times_for_production_day_are_those_of_its_weekday(
    tenant_db, day_of_sale, pickup_times
):
    point_of_sale = PointOfSaleFactory(
        pickup_times=[(4, "14:00", "19:00"), (1, "09:30", "12:00")]
    )
    production_day = ProductionDayFactory(day_of_sale=day_of_sale)

    assert [
        str(pickup_time)
        for pickup_time in point_of_sale.pickup_times_for(production_day)
    ] == pickup_times


@pytest.mark.parametrize(
    "details, summary",
    [
        # Nothing to say when and where: the description alone is no summary.
        ({"description": "Klingeln bei Müller"}, ""),
        ({"city": "Leipzig"}, "Leipzig"),
        (
            {"pickup_times": [(4, "14:00", "19:00"), (1, "09:30", "12:00")]},
            "Dienstag, 09:30–12:00 Uhr · Freitag, 14:00–19:00 Uhr",
        ),
        (
            {
                "street": "Große Fleischergasse",
                "street_number": "12a",
                "postal_code": "04109",
                "city": "Leipzig",
                "pickup_times": [(4, "14:00", "19:00")],
            },
            "Freitag, 14:00–19:00 Uhr · Große Fleischergasse 12a, 04109 Leipzig",
        ),
    ],
)
def test_point_of_sale_summary_names_pickup_times_and_address(
    tenant_db, details, summary
):
    assert PointOfSaleFactory(**details).summary_for() == summary
