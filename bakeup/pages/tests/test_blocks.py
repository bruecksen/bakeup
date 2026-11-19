import pytest
from bs4 import BeautifulSoup

from bakeup.pages.blocks import (
    FaqBlock,
    ImageTextBlock,
    PointsOfSaleBlock,
    SectionBlock,
)
from bakeup.pages.tests.factories import ContentPageFactory, ImageFactory
from bakeup.shop.tests.factories import PointOfSaleFactory

QUESTIONS = [
    {
        "question": "Wann kann ich bestellen?",
        "answer": "<p>Bis zum Bestellschluss.</p>",
    },
    {
        "question": "Wo hole ich mein Brot ab? <Laden & Markt>",
        "answer": "<p>An deiner Abholstelle.</p>",
    },
]


def render(block, value):
    return BeautifulSoup(block.render(block.to_python(value)), "html.parser")


def test_faq_renders_every_question_with_its_answer_collapsed():
    html = render(FaqBlock(), {"heading": "Häufige Fragen", "items": QUESTIONS})

    buttons = html.select(".accordion-button")
    answers = html.select(".accordion-collapse")
    assert html.select_one("h2").get_text(strip=True) == "Häufige Fragen"
    assert [
        (b.get_text(strip=True), b["class"], b["aria-expanded"]) for b in buttons
    ] == [
        ("Wann kann ich bestellen?", ["accordion-button", "collapsed"], "false"),
        (
            "Wo hole ich mein Brot ab? <Laden & Markt>",
            ["accordion-button", "collapsed"],
            "false",
        ),
    ]
    assert [(a["class"], a.get_text(strip=True)) for a in answers] == [
        (["accordion-collapse", "collapse"], "Bis zum Bestellschluss."),
        (["accordion-collapse", "collapse"], "An deiner Abholstelle."),
    ]
    assert [b["data-bs-target"] for b in buttons] == ["#" + a["id"] for a in answers]


def test_faq_without_heading_renders_no_heading_element():
    html = render(FaqBlock(), {"heading": "", "items": QUESTIONS[:1]})

    assert html.select("h2") == []


def test_two_faqs_on_one_page_get_different_collapse_ids(client, shop_page):
    faq = {"type": "faq", "value": {"heading": "", "items": QUESTIONS[:1]}}
    page = ContentPageFactory(parent=shop_page, content=[faq, faq])

    response = client.get(page.url)

    html = BeautifulSoup(response.content, "html.parser")
    ids = [a["id"] for a in html.select(".faq .accordion-collapse")]
    assert len(ids) == 2, "expected one answer per FAQ block"
    assert ids[0] != ids[1]


@pytest.mark.parametrize(
    "position, image_order, text_order",
    [("left", "order-lg-1", "order-lg-2"), ("right", "order-lg-2", "order-lg-1")],
)
def test_image_text_puts_the_image_on_the_chosen_side(
    tenant_db, position, image_order, text_order
):
    html = render(
        ImageTextBlock(),
        {
            "image": ImageFactory().pk,
            "image_position": position,
            "eyebrow": "Unsere Backstube",
            "heading": "Handwerk",
            "text": "<p>Brot mit Zeit.</p>",
            "buttons": [],
        },
    )

    assert html.select_one(".image-text-image")["class"] == [
        "col-12",
        "col-lg-6",
        "image-text-image",
        image_order,
    ]
    assert html.select_one(".image-text-body")["class"] == [
        "col-12",
        "col-lg-6",
        "image-text-body",
        text_order,
    ]


def test_image_text_renders_without_eyebrow_heading_and_buttons(tenant_db):
    html = render(
        ImageTextBlock(),
        {
            "image": ImageFactory().pk,
            "image_position": "left",
            "eyebrow": "",
            "heading": "",
            "text": "<p>Brot mit Zeit.</p>",
            "buttons": [],
        },
    )

    assert html.select(".block-heading, .image-text-buttons") == []
    assert html.select_one(".richtext-body").get_text(strip=True) == "Brot mit Zeit."
    assert html.select_one("img")["class"] == ["img-fluid", "rounded"]


@pytest.mark.parametrize(
    "background, expected_class",
    [
        ("transparent", None),
        ("white", "bg-white"),
        ("primary", "text-bg-primary"),
    ],
)
def test_section_background_ends_up_as_class(background, expected_class):
    html = render(
        SectionBlock(),
        {"background": background, "eyebrow": "", "heading": "", "content": []},
    )

    expected = ["section-band", f"section-band-{background}", expected_class, "py-5"]
    assert html.select_one("section")["class"] == [c for c in expected if c]


def test_section_renders_its_heading_and_nested_blocks():
    html = render(
        SectionBlock(),
        {
            "background": "dark",
            "eyebrow": "Seit 1924",
            "heading": "Unsere Backstube",
            "content": [
                {
                    "type": "text",
                    "value": {"text": "<p>Brot mit Zeit.</p>", "alignment": "center"},
                },
                {
                    "type": "faq",
                    "value": {"heading": "", "items": QUESTIONS[:1]},
                },
            ],
        },
    )

    section = html.select_one("section")
    assert section.select_one(".eyebrow").get_text(strip=True) == "Seit 1924"
    assert section.select_one("h2").get_text(strip=True) == "Unsere Backstube"
    assert section.select_one(".richtext-body")["class"] == [
        "text-center",
        "richtext-body",
    ]
    assert section.select_one(".richtext-body").get_text(strip=True) == "Brot mit Zeit."
    assert section.select_one(".accordion-button").get_text(strip=True) == (
        "Wann kann ich bestellen?"
    )


def test_points_of_sale_block_lists_public_points_of_sale(tenant_db):
    PointOfSaleFactory(name="Markt", pickup_times=[(5, "09:00", "12:00")])
    PointOfSaleFactory(name="Hofladen", city="Leipzig")
    PointOfSaleFactory(name="Lieferung Café", is_internal=True)

    html = render(
        PointsOfSaleBlock(), {"heading": "Abholstellen", "display": "map_and_list"}
    )

    assert html.select_one("h2").get_text(strip=True) == "Abholstellen"
    assert [
        (
            card.select_one(".card-title").get_text(strip=True),
            [
                element.get_text(strip=True)
                for element in card.select(".pos-address, .pos-pickup-times")
            ],
        )
        for card in html.select(".pos-card")
    ] == [("Hofladen", ["Leipzig"]), ("Markt", ["Samstag, 09:00–12:00 Uhr"])]


@pytest.mark.parametrize(
    "display, api_key, map_count, card_count",
    [
        ("map_and_list", "test-key", 1, 1),
        ("map", "test-key", 1, 0),
        ("list", "test-key", 0, 1),
        # Map only, but no map can be shown: the list instead of nothing.
        ("map", "", 0, 1),
    ],
)
def test_points_of_sale_block_shows_map_and_list_as_chosen(
    tenant_db, settings, display, api_key, map_count, card_count
):
    settings.SMARTMAPS_API_KEY = api_key
    PointOfSaleFactory(name="Hofladen", latitude="51.339700", longitude="12.373100")

    html = render(PointsOfSaleBlock(), {"heading": "", "display": display})

    assert html.select("h2") == []
    assert len(html.select("[data-pos-map]")) == map_count
    assert len(html.select(".pos-card")) == card_count
    # The button that shows a card's pin needs both the map and the list.
    assert len(html.select("[data-pos-focus]")) == map_count * card_count


def test_two_points_of_sale_blocks_on_one_page_get_different_map_ids(
    client, shop_page, settings
):
    settings.SMARTMAPS_API_KEY = "test-key"
    PointOfSaleFactory(name="Hofladen", latitude="51.339700", longitude="12.373100")
    block = {
        "type": "points_of_sale",
        "value": {"heading": "", "display": "map_and_list"},
    }
    page = ContentPageFactory(parent=shop_page, content=[block, block])

    response = client.get(page.url)

    html = BeautifulSoup(response.content, "html.parser")
    maps = html.select("[data-pos-map]")
    assert len(maps) == 2, "expected one map per block"
    assert len({m["id"] for m in maps}) == 2
    assert len({m["data-markers"] for m in maps}) == 2
    assert [html.find("script", id=m["data-markers"]) is not None for m in maps] == [
        True,
        True,
    ]
