from datetime import timedelta

import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from django.utils import timezone

from bakeup.pages.tests.factories import EmailSettingsFactory, PointOfSalePageFactory
from bakeup.shop.models import (
    CustomerOrderPosition,
    CustomerOrderTemplateSkip,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.shop.tests.factories import (
    CustomerOrderFactory,
    CustomerOrderPositionFactory,
    CustomerOrderTemplateFactory,
    CustomerOrderTemplatePositionFactory,
    CustomerOrderTemplateSkipFactory,
    PointOfSaleFactory,
    ProductionDayFactory,
)
from bakeup.users.tests.factories import UserFactory
from bakeup.workshop.tests.factories import ProductionDayProductFactory


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


def order_positions():
    return list(
        CustomerOrderPosition.objects.order_by(
            "order__production_day__day_of_sale", "product__name"
        ).values_list(
            "order__customer", "order__production_day", "product__name", "quantity"
        )
    )


def skips():
    return list(
        CustomerOrderTemplateSkip.objects.order_by("product__name").values_list(
            "customer", "production_day", "product__name"
        )
    )


def sent_mails(mailoutbox):
    return [(mail.to, mail.subject) for mail in mailoutbox]


def shown_messages(response):
    # Of a followed response: the messages the page after the redirect shows.
    return [str(message) for message in response.context["messages"]]


@pytest.fixture
def order_mails(tenant_db):
    # Confirmation and cancellation mails are sent, with subjects to tell
    # them apart.
    return EmailSettingsFactory(
        email_subject_prefix="",
        send_email_order_confirm=True,
        email_order_confirm_subject="Bestellt",
        send_email_order_cancellation=True,
        email_order_cancellation_subject="Storniert",
    )


def test_cancelled_abo_order_stays_cancelled_through_the_life_of_a_production_day(
    client,
    customer,
    staff_user,
    abo_products,
    order_mails,
    production_day_form_data,
    mailoutbox,
):
    # Regression test for #608: an abo order came back after it was cancelled.
    bread, broetchen = abo_products["Bread"], abo_products["Brötchen"]
    abo = CustomerOrderTemplateFactory(customer=customer)
    CustomerOrderTemplatePositionFactory(order_template=abo, product=bread, quantity=2)
    CustomerOrderTemplatePositionFactory(
        order_template=abo, product=broetchen, quantity=3
    )
    email = customer.user.email
    day_of_sale = timezone.now().date() + timedelta(days=7)

    # 1. Staff create a day with the published bread: the abo order is created.
    client.force_login(staff_user)
    response = client.post(
        reverse("workshop:production-day-add"),
        production_day_form_data(
            day_of_sale, [{"product": bread, "is_published": True}]
        ),
        follow=True,
    )
    day = ProductionDay.objects.get()
    assert response.redirect_chain == [
        (reverse("workshop:production-day-detail", kwargs={"pk": day.pk}), 302)
    ]
    assert order_positions() == [(customer.pk, day.pk, "Bread", 2)]
    assert sent_mails(mailoutbox) == [([email], "Bestellt")]
    assert shown_messages(response) == ["1 Abo-Bestellung für Bread angelegt."]

    # 2. The customer cancels the order in the shop.
    client.force_login(customer.user)
    response = client.post(
        reverse("shop:customer-order-add", kwargs={"production_day": day.pk}),
        {"cancel": ""},
        follow=True,
    )
    assert response.redirect_chain == [(reverse("shop:order-list"), 302)]
    assert order_positions() == []
    assert sent_mails(mailoutbox) == [([email], "Bestellt"), ([email], "Storniert")]

    # 3. Staff move the day and describe it: no order, no mail, no message.
    client.force_login(staff_user)
    day_url = reverse("workshop:production-day-update", kwargs={"pk": day.pk})
    saved = [(reverse("workshop:production-day-detail", kwargs={"pk": day.pk}), 302)]
    bread_row = ProductionDayProduct.objects.get(production_day=day, product=bread)
    bread_row_data = {"id": bread_row.pk, "product": bread, "is_published": True}
    day_of_sale += timedelta(days=1)
    response = client.post(
        day_url,
        production_day_form_data(
            day_of_sale, [bread_row_data], description="Mit Sauerteig"
        ),
        follow=True,
    )
    assert response.redirect_chain == saved
    day.refresh_from_db()
    assert (day.day_of_sale, day.description) == (day_of_sale, "Mit Sauerteig")
    assert order_positions() == []
    assert len(mailoutbox) == 2
    assert shown_messages(response) == []

    # 4. Staff add the published Brötchen: an order with the Brötchen only.
    response = client.post(
        day_url,
        production_day_form_data(
            day_of_sale,
            [bread_row_data, {"product": broetchen, "is_published": True}],
        ),
        follow=True,
    )
    assert response.redirect_chain == saved
    assert order_positions() == [(customer.pk, day.pk, "Brötchen", 3)]
    assert sent_mails(mailoutbox)[2:] == [([email], "Bestellt")]
    assert shown_messages(response) == ["1 Abo-Bestellung für Brötchen angelegt."]

    # 5. Staff remove the Brötchen, which asks for a confirmation because of
    # the order, and add them back: the removed order is not created again.
    broetchen_row = ProductionDayProduct.objects.get(
        production_day=day, product=broetchen
    )
    response = client.post(
        day_url,
        production_day_form_data(
            day_of_sale,
            [
                bread_row_data,
                {"id": broetchen_row.pk, "product": broetchen, "DELETE": True},
            ],
        ),
        follow=True,
    )
    confirm_url = reverse(
        "workshop:production-day-product-delete", kwargs={"pk": broetchen_row.pk}
    )
    assert response.redirect_chain == [(confirm_url, 302)]
    response = client.post(confirm_url, follow=True)
    assert response.redirect_chain == saved
    assert order_positions() == []
    response = client.post(
        day_url,
        production_day_form_data(
            day_of_sale,
            [bread_row_data, {"product": broetchen, "is_published": True}],
        ),
        follow=True,
    )
    assert response.redirect_chain == saved
    assert list(
        ProductionDayProduct.objects.filter(production_day=day)
        .order_by("product__name")
        .values_list("product__name", "is_published")
    ) == [("Bread", True), ("Brötchen", True)]
    assert order_positions() == []
    assert len(mailoutbox) == 3
    assert shown_messages(response) == []
    assert skips() == [
        (customer.pk, day.pk, "Bread"),
        (customer.pk, day.pk, "Brötchen"),
    ]


def test_cancelling_an_abo_order_records_the_opt_out_and_a_day_save_keeps_it_cancelled(
    client,
    customer,
    staff_user,
    abo_products,
    order_mails,
    production_day_form_data,
    mailoutbox,
):
    # Regression test for #608: an abo order came back after it was cancelled.
    bread = abo_products["Bread"]
    CustomerOrderTemplatePositionFactory(
        order_template__customer=customer, product=bread
    )
    row = ProductionDayProductFactory(product=bread, is_published=True)
    day = row.production_day
    order = CustomerOrderFactory(customer=customer, production_day=day)
    CustomerOrderPositionFactory(order=order, product=bread)
    client.force_login(customer.user)

    response = client.post(
        reverse("shop:customer-order-add", kwargs={"production_day": day.pk}),
        {"cancel": ""},
    )

    assert response.status_code == 302
    assert order_positions() == []
    assert skips() == [(customer.pk, day.pk, "Bread")]

    client.force_login(staff_user)
    response = client.post(
        reverse("workshop:production-day-update", kwargs={"pk": day.pk}),
        production_day_form_data(
            day.day_of_sale,
            [{"id": row.pk, "product": bread, "is_published": True}],
            description="Mit Sauerteig",
        ),
    )

    assert response.status_code == 302, response.content.decode()[:500]
    assert order_positions() == []
    assert sent_mails(mailoutbox) == [([customer.user.email], "Storniert")]


def test_ordering_zero_of_one_abo_product_records_the_opt_out_for_that_product_only(
    client, customer, abo_products
):
    bread, broetchen = abo_products["Bread"], abo_products["Brötchen"]
    abo = CustomerOrderTemplateFactory(customer=customer)
    day = ProductionDayFactory()
    order = CustomerOrderFactory(customer=customer, production_day=day)
    for product in [bread, broetchen]:
        CustomerOrderTemplatePositionFactory(order_template=abo, product=product)
        ProductionDayProductFactory(
            production_day=day, product=product, is_published=True
        )
        CustomerOrderPositionFactory(order=order, product=product, quantity=2)
    client.force_login(customer.user)

    response = client.post(
        reverse("shop:customer-order-add", kwargs={"production_day": day.pk}),
        {"update": "", f"product-{bread.pk}": 0, f"product-{broetchen.pk}": 2},
    )

    assert response.status_code == 302
    assert order_positions() == [(customer.pk, day.pk, "Brötchen", 2)]
    assert skips() == [(customer.pk, day.pk, "Bread")]


def test_removing_a_product_that_is_not_in_the_abo_records_no_opt_out(
    client, customer, abo_products
):
    bread, baguette = abo_products["Bread"], abo_products["Baguette"]
    CustomerOrderTemplatePositionFactory(
        order_template__customer=customer, product=bread
    )
    day = ProductionDayFactory()
    order = CustomerOrderFactory(customer=customer, production_day=day)
    for product in [bread, baguette]:
        ProductionDayProductFactory(
            production_day=day, product=product, is_published=True
        )
        CustomerOrderPositionFactory(order=order, product=product)
    client.force_login(customer.user)

    response = client.post(
        reverse("shop:customer-order-add", kwargs={"production_day": day.pk}),
        {"update": "", f"product-{bread.pk}": 1, f"product-{baguette.pk}": 0},
    )

    assert response.status_code == 302
    assert order_positions() == [(customer.pk, day.pk, "Bread", 1)]
    assert skips() == []


def test_subscribing_at_checkout_does_not_recreate_the_order_of_a_cancelled_day(
    client, customer, abo_products
):
    bread = abo_products["Bread"]
    today = timezone.now().date()
    cancelled_day = ProductionDayFactory(day_of_sale=today + timedelta(days=3))
    open_day = ProductionDayFactory(day_of_sale=today + timedelta(days=4))
    checkout_day = ProductionDayFactory(day_of_sale=today + timedelta(days=5))
    for day in [cancelled_day, open_day, checkout_day]:
        ProductionDayProductFactory(
            production_day=day, product=bread, is_published=True
        )
    CustomerOrderTemplateSkipFactory(
        customer=customer, production_day=cancelled_day, product=bread
    )
    client.force_login(customer.user)

    response = client.post(
        reverse("shop:customer-order-add", kwargs={"production_day": checkout_day.pk}),
        {"create": "", f"product-{bread.pk}": 2, f"productabo-{bread.pk}": "on"},
    )

    assert response.status_code == 302
    assert order_positions() == [
        (customer.pk, open_day.pk, "Bread", 2),
        (customer.pk, checkout_day.pk, "Bread", 2),
    ]


def test_changing_the_abo_creates_the_orders_of_upcoming_published_days(
    client, customer, abo_products
):
    bread, broetchen = abo_products["Bread"], abo_products["Brötchen"]
    abo = CustomerOrderTemplateFactory(customer=customer)
    CustomerOrderTemplatePositionFactory(order_template=abo, product=bread, quantity=1)
    today = timezone.now().date()
    published_day = ProductionDayFactory(day_of_sale=today + timedelta(days=3))
    ProductionDayProductFactory(
        production_day=published_day, product=broetchen, is_published=True
    )
    unpublished_day = ProductionDayFactory(day_of_sale=today + timedelta(days=4))
    ProductionDayProductFactory(
        production_day=unpublished_day, product=broetchen, is_published=False
    )
    # A day that is open for ordering, but not for the abo product.
    mixed_day = ProductionDayFactory(day_of_sale=today + timedelta(days=5))
    ProductionDayProductFactory(
        production_day=mixed_day, product=abo_products["Baguette"], is_published=True
    )
    ProductionDayProductFactory(
        production_day=mixed_day, product=broetchen, is_published=False
    )
    client.force_login(customer.user)

    response = client.post(
        reverse("shop:customer-order-template-update", kwargs={"pk": abo.pk}),
        {f"productabo-{broetchen.pk}": 4},
    )

    assert response.status_code == 302
    assert response.url == reverse("shop:order-list")
    assert order_positions() == [(customer.pk, published_day.pk, "Brötchen", 4)]
