from decimal import Decimal

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse

from bakeup.shop.models import PointOfSale
from bakeup.shop.tests.factories import PointOfSaleFactory
from bakeup.users.tests.factories import UserFactory

DETAILS = {
    "name": "Hofladen Müller",
    "short_name": "Hof",
    "is_primary": "on",
    "street": "Große Fleischergasse",
    "street_number": "12a",
    "postal_code": "04109",
    "city": "Leipzig",
    "description": "Eingang über den Hof.\nBitte klingeln.",
    "latitude": "51.339700",
    "longitude": "12.373100",
    "pickup_times-TOTAL_FORMS": "2",
    "pickup_times-INITIAL_FORMS": "0",
    "pickup_times-0-day_of_the_week": "4",
    "pickup_times-0-from_time": "14:00",
    "pickup_times-0-to_time": "19:00",
    "pickup_times-1-day_of_the_week": "1",
    "pickup_times-1-from_time": "09:30",
    "pickup_times-1-to_time": "12:00",
}
SAVED_PICKUP_TIMES = ["Dienstag, 09:30–12:00 Uhr", "Freitag, 14:00–19:00 Uhr"]
SAVED_DETAILS = {
    "name": "Hofladen Müller",
    "short_name": "Hof",
    "is_primary": True,
    "is_internal": False,
    "street": "Große Fleischergasse",
    "street_number": "12a",
    "postal_code": "04109",
    "city": "Leipzig",
    "description": "Eingang über den Hof.\nBitte klingeln.",
    "latitude": Decimal("51.339700"),
    "longitude": Decimal("12.373100"),
}
EMPTY_DETAILS = {
    "name": "Laden",
    "short_name": None,
    "is_primary": False,
    "is_internal": False,
    "street": None,
    "street_number": None,
    "postal_code": None,
    "city": None,
    "description": "",
    "latitude": None,
    "longitude": None,
}


def saved(point_of_sale):
    return PointOfSale.objects.values(*SAVED_DETAILS).get(pk=point_of_sale.pk)


def saved_pickup_times(point_of_sale):
    return [str(pickup_time) for pickup_time in point_of_sale.pickup_times.all()]


@pytest.fixture
def point_of_sale(tenant_db):
    return PointOfSaleFactory(name="Laden")


@pytest.fixture(params=["point-of-sale-add", "point-of-sale-update"])
def form_url(request, point_of_sale):
    if request.param == "point-of-sale-add":
        return reverse("workshop:point-of-sale-add")
    return reverse("workshop:point-of-sale-update", kwargs={"pk": point_of_sale.pk})


def test_anonymous_user_is_redirected_to_login_from_point_of_sale_form(
    client, form_url, point_of_sale
):
    response = client.post(form_url, DETAILS)

    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))
    assert [saved(pos) for pos in PointOfSale.objects.all()] == [EMPTY_DETAILS]


def test_customer_cannot_save_point_of_sale(client, form_url, point_of_sale):
    client.force_login(UserFactory(is_staff=False))

    response = client.post(form_url, DETAILS)

    assert response.status_code == 403
    assert [saved(pos) for pos in PointOfSale.objects.all()] == [EMPTY_DETAILS]


def test_staff_user_creates_point_of_sale_with_all_details(client, tenant_db):
    client.force_login(UserFactory(is_staff=True))

    response = client.post(reverse("workshop:point-of-sale-add"), DETAILS)

    assert response.status_code == 302
    assert response.url == reverse("workshop:point-of-sale-list")
    [point_of_sale] = PointOfSale.objects.all()
    assert saved(point_of_sale) == SAVED_DETAILS
    assert saved_pickup_times(point_of_sale) == SAVED_PICKUP_TIMES
    assert saved_pickup_times(point_of_sale) == SAVED_PICKUP_TIMES


def test_staff_user_updates_point_of_sale_with_all_details(client, point_of_sale):
    client.force_login(UserFactory(is_staff=True))

    response = client.post(
        reverse("workshop:point-of-sale-update", kwargs={"pk": point_of_sale.pk}),
        DETAILS,
    )

    assert response.status_code == 302
    assert response.url == reverse("workshop:point-of-sale-list")
    assert saved(point_of_sale) == SAVED_DETAILS
    assert saved_pickup_times(point_of_sale) == SAVED_PICKUP_TIMES


def test_staff_user_saves_point_of_sale_with_only_a_name(client, tenant_db):
    point_of_sale = PointOfSaleFactory(
        name="Hofladen",
        street="Große Fleischergasse",
        city="Leipzig",
        description="Eingang über den Hof.",
        pickup_times=[(4, "16:00", "18:00")],
        latitude=Decimal("51.339700"),
        longitude=Decimal("12.373100"),
    )
    client.force_login(UserFactory(is_staff=True))

    # Every optional field is sent empty, as when the pin is removed and the
    # inputs are cleared.
    response = client.post(
        reverse("workshop:point-of-sale-update", kwargs={"pk": point_of_sale.pk}),
        {
            "name": "Laden",
            "short_name": "",
            "street": "",
            "street_number": "",
            "postal_code": "",
            "city": "",
            "description": "",
            "latitude": "",
            "longitude": "",
            "pickup_times-TOTAL_FORMS": "0",
            "pickup_times-INITIAL_FORMS": "0",
        },
    )

    assert response.status_code == 302
    assert saved(point_of_sale) == EMPTY_DETAILS


@pytest.mark.parametrize(
    "api_key, map_count",
    [("", 0), ("test-key", 1)],
)
def test_pin_picker_is_only_shown_with_a_map_key(
    client, point_of_sale, settings, api_key, map_count
):
    settings.SMARTMAPS_API_KEY = api_key
    client.force_login(UserFactory(is_staff=True))

    response = client.get(
        reverse("workshop:point-of-sale-update", kwargs={"pk": point_of_sale.pk})
    )

    assert response.status_code == 200
    html = BeautifulSoup(response.content, "html.parser")
    assert len(html.select("[data-pos-map]")) == map_count
    assert len(html.select("[data-pos-map-remove]")) == map_count
    assert len(html.select("[data-pos-map-search]")) == map_count
    assert [i["type"] for i in html.select("#id_latitude, #id_longitude")] == [
        "hidden",
        "hidden",
    ]


def test_staff_user_changes_and_removes_pickup_times(client, tenant_db):
    point_of_sale = PointOfSaleFactory(
        name="Laden", pickup_times=[(4, "14:00", "19:00"), (5, "09:00", "12:00")]
    )
    friday, saturday = point_of_sale.pickup_times.all()
    client.force_login(UserFactory(is_staff=True))

    response = client.post(
        reverse("workshop:point-of-sale-update", kwargs={"pk": point_of_sale.pk}),
        {
            "name": "Laden",
            "pickup_times-TOTAL_FORMS": "3",
            "pickup_times-INITIAL_FORMS": "2",
            "pickup_times-0-id": friday.pk,
            "pickup_times-0-day_of_the_week": "4",
            "pickup_times-0-from_time": "15:00",
            "pickup_times-0-to_time": "18:30",
            "pickup_times-1-id": saturday.pk,
            "pickup_times-1-day_of_the_week": "5",
            "pickup_times-1-from_time": "09:00",
            "pickup_times-1-to_time": "12:00",
            "pickup_times-1-DELETE": "on",
            # A row that was added and left empty is ignored.
            "pickup_times-2-day_of_the_week": "",
            "pickup_times-2-from_time": "",
            "pickup_times-2-to_time": "",
        },
    )

    assert response.status_code == 302
    assert saved_pickup_times(point_of_sale) == ["Freitag, 15:00–18:30 Uhr"]


def test_pickup_time_that_ends_before_it_starts_is_rejected(client, point_of_sale):
    client.force_login(UserFactory(is_staff=True))

    response = client.post(
        reverse("workshop:point-of-sale-update", kwargs={"pk": point_of_sale.pk}),
        {
            "name": "Hofladen",
            "pickup_times-TOTAL_FORMS": "1",
            "pickup_times-INITIAL_FORMS": "0",
            "pickup_times-0-day_of_the_week": "4",
            "pickup_times-0-from_time": "19:00",
            "pickup_times-0-to_time": "14:00",
        },
    )

    assert response.status_code == 200
    assert response.context["pickup_time_formset"].errors == [
        {"to_time": ["Die Abholung muss nach ihrem Beginn enden."]}
    ]
    # Nothing is saved, not even the valid name.
    assert saved(point_of_sale) == EMPTY_DETAILS
    assert saved_pickup_times(point_of_sale) == []
