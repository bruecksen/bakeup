from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from bakeup.pages.tests.factories import PointOfSalePageFactory
from bakeup.shop.tests.factories import (
    CustomerOrderFactory,
    PointOfSaleFactory,
    ProductionDayFactory,
)
from bakeup.users.tests.factories import UserFactory


def options(response, form_selector):
    """
    The options of the point of sale select of a form, with what the dropdown
    shows below the name.
    """
    html = BeautifulSoup(response.content, "html.parser")
    return [
        [
            option.get_text(strip=True),
            option.get("data-address"),
            option.get("data-pickup-times"),
        ]
        for option in html.select(f"{form_selector} select[name=point_of_sale] option")
    ]


@pytest.fixture
def customer(shop_page):
    return UserFactory().customer


@pytest.fixture
def order_with_two_points_of_sale(customer):
    def create(**details):
        shop = PointOfSaleFactory(name="Laden", **details)
        market = PointOfSaleFactory(name="Markt")
        # The next Friday, the weekday decides which pick-up times are shown.
        today = timezone.now().date()
        production_day = ProductionDayFactory(
            day_of_sale=today + timedelta(days=(4 - today.weekday()) % 7 or 7)
        )
        production_day.point_of_sales.set([shop, market])
        order = CustomerOrderFactory(
            customer=customer, production_day=production_day, point_of_sale=shop
        )
        return order, shop, market

    return create


def test_anonymous_user_is_redirected_to_login_from_order_list(client, shop_page):
    response = client.get(reverse("shop:order-list"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("shop:login"))


def test_checkout_options_carry_address_and_pickup_times_for_the_dropdown(
    client, customer, order_with_two_points_of_sale
):
    order, shop, market = order_with_two_points_of_sale(
        street="Große Fleischergasse",
        street_number="12a",
        postal_code="04109",
        city="Leipzig",
        pickup_times=[(4, "16:00", "18:00"), (5, "09:00", "12:00")],
    )
    client.force_login(customer.user)

    response = client.get(reverse("shop:order-list"))

    assert response.status_code == 200
    form = f"#customer-order-form-{order.pk}"
    assert sorted(options(response, form)) == [
        [
            "Laden",
            "Große Fleischergasse 12a, 04109 Leipzig",
            # Only the pick-up time on the weekday of the production day.
            "Freitag, 16:00–18:00 Uhr",
        ],
        ["Markt", None, None],
    ]
    html = BeautifulSoup(response.content, "html.parser")
    assert len(html.select(f"{form} select[data-pos-dropdown]")) == 1
    # No point of sale page, so no link to it.
    assert html.select(f"{form} .pos-overview-link") == []


def test_checkout_links_to_the_point_of_sale_page(
    client, customer, shop_page, order_with_two_points_of_sale
):
    order, shop, market = order_with_two_points_of_sale(city="Leipzig")
    page = PointOfSalePageFactory(parent=shop_page, title="Abholstellen")
    client.force_login(customer.user)

    response = client.get(reverse("shop:order-list"))

    html = BeautifulSoup(response.content, "html.parser")
    assert [
        a["href"]
        for a in html.select(f"#customer-order-form-{order.pk} a.pos-overview-link")
    ] == [page.get_url(response.wsgi_request)]


def test_checkout_is_unchanged_when_no_point_of_sale_has_pickup_times_or_address(
    client, customer, shop_page, order_with_two_points_of_sale
):
    order, shop, market = order_with_two_points_of_sale(
        description="Eingang über den Hof."
    )
    PointOfSalePageFactory(parent=shop_page, title="Abholstellen")
    client.force_login(customer.user)

    response = client.get(reverse("shop:order-list"))

    assert response.status_code == 200
    assert sorted(options(response, f"#customer-order-form-{order.pk}")) == [
        ["Laden", None, None],
        ["Markt", None, None],
    ]
    html = BeautifulSoup(response.content, "html.parser")
    # The plain select, nothing for the script to turn into a dropdown.
    assert html.select("[data-pos-dropdown], .pos-overview-link") == []


def test_signup_options_carry_address_and_pickup_times_for_the_dropdown(
    client, shop_page
):
    PointOfSaleFactory(
        name="Laden <Müller & Söhne>",
        city="Leipzig",
        pickup_times=[(4, "16:00", "18:00"), (5, "09:00", "12:00")],
    )
    PointOfSaleFactory(name="Markt")
    page = PointOfSalePageFactory(parent=shop_page, title="Abholstellen")

    response = client.get(reverse("shop:signup"))

    assert response.status_code == 200
    assert options(response, "#signup_form") == [
        [
            "Laden <Müller & Söhne>",
            "Leipzig",
            "Freitag, 16:00–18:00 Uhr · Samstag, 09:00–12:00 Uhr",
        ],
        ["Markt", None, None],
    ]
    html = BeautifulSoup(response.content, "html.parser")
    assert len(html.select("#signup_form select[data-pos-dropdown]")) == 1
    assert [a["href"] for a in html.select("#signup_form #div_id_point_of_sale a")] == [
        page.get_url(response.wsgi_request)
    ]


@pytest.mark.parametrize(
    "names, names_in_select",
    [
        # More than one point of sale: a select, as before.
        (["Laden", "Markt"], ["Laden", "Markt"]),
        # A single point of sale: nothing to choose, although it has pick-up
        # times.
        (["Laden"], []),
    ],
)
def test_signup_keeps_the_select_without_address_and_pickup_times(
    client, shop_page, names, names_in_select
):
    for name in names:
        PointOfSaleFactory(
            name=name,
            description="Eingang über den Hof.",
            pickup_times=[(4, "16:00", "18:00")] if len(names) == 1 else [],
        )

    response = client.get(reverse("shop:signup"))

    assert response.status_code == 200
    html = BeautifulSoup(response.content, "html.parser")
    assert [
        option.get_text(strip=True)
        for option in html.select("#signup_form select#id_point_of_sale option")
    ] == names_in_select
    # The plain select, nothing for the script to turn into a dropdown.
    assert html.select("[data-pos-dropdown], [data-address], [data-pickup-times]") == []


def test_customer_changes_point_of_sale_in_profile_with_the_detailed_select(
    client, customer
):
    PointOfSaleFactory(name="Laden", city="Leipzig")
    market = PointOfSaleFactory(name="Markt")
    client.force_login(customer.user)

    response = client.get(reverse("shop:user-profile"))

    assert response.status_code == 200
    assert options(response, "#user_profile") == [
        ["Laden", "Leipzig", None],
        ["Markt", None, None],
    ]

    form = response.context["forms"]["user_profile"]
    data = {
        name: value
        for name, value in form.initial.items()
        if name in form.fields and value is not None
    }
    data.update({"point_of_sale": market.pk, "action": "user_profile"})
    response = client.post(reverse("shop:user-profile"), data)

    customer.refresh_from_db()
    assert customer.point_of_sale == market, response.content.decode()[:500]
