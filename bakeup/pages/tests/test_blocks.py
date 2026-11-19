import pytest
from bs4 import BeautifulSoup

from bakeup.pages.blocks import FaqBlock, ImageTextBlock, SectionBlock
from bakeup.pages.tests.factories import ContentPageFactory, ImageFactory
from bakeup.workshop.models import Category
from bakeup.workshop.tests.factories import (
    ProductFactory,
    ProductionDayProductFactory,
)

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


def assortment(only_planned_products=False):
    return {
        "type": "product_assortment",
        "value": {"only_planned_products": only_planned_products},
    }


def get_assortment_categories(client, page):
    """The categories of every assortment on the page: name, open, product names."""
    html = BeautifulSoup(client.get(page.url).content, "html.parser")
    categories = []
    for item in html.select(".product-assortment .accordion-item"):
        button = item.select_one(".accordion-button")
        badge = button.select_one(".badge").extract()
        collapse = item.select_one(".accordion-collapse")
        assert button["data-bs-target"] == "#" + collapse["id"]
        is_open = "show" in collapse["class"]
        assert ("collapsed" in button["class"]) is not is_open
        assert button["aria-expanded"] == ("true" if is_open else "false")
        # The first text of the title is the name, the weight follows in a span.
        names = [next(t.stripped_strings) for t in item.select(".card-title")]
        assert badge.get_text(strip=True) == str(len(names))
        categories.append((button.get_text(strip=True), is_open, names))
    return categories


def test_assortment_with_several_categories_is_collapsed(client, shop_page):
    bread = Category.add_root(name="Brot & Brötchen", slug="brot")
    cake = Category.add_root(name="Kuchen", slug="kuchen")
    ProductFactory(name="Roggenbrot", category=bread, is_sellable=True)
    ProductFactory(name="Dinkelbrot", category=bread, is_sellable=True)
    ProductFactory(name="Käsekuchen", category=cake, is_sellable=True)
    ProductFactory(name="Gutschein", category=None, is_sellable=True)
    ProductFactory(name="Sauerteig", category=bread, is_sellable=False)
    page = ContentPageFactory(parent=shop_page, content=[assortment()])

    assert get_assortment_categories(client, page) == [
        ("Brot & Brötchen", False, ["Dinkelbrot", "Roggenbrot"]),
        ("Kuchen", False, ["Käsekuchen"]),
        ("Weitere", False, ["Gutschein"]),
    ]


def test_assortment_with_a_single_category_is_open(client, shop_page):
    bread = Category.add_root(name="Brot", slug="brot")
    ProductFactory(name="Roggenbrot", category=bread, is_sellable=True)
    ProductFactory(name="Dinkelbrot", category=bread, is_sellable=True)
    page = ContentPageFactory(parent=shop_page, content=[assortment()])

    assert get_assortment_categories(client, page) == [
        ("Brot", True, ["Dinkelbrot", "Roggenbrot"]),
    ]


def test_assortment_of_planned_products_leaves_out_unplanned_categories(
    client, shop_page
):
    bread = Category.add_root(name="Brot", slug="brot")
    cake = Category.add_root(name="Kuchen", slug="kuchen")
    planned = ProductFactory(name="Roggenbrot", category=bread, is_sellable=True)
    ProductFactory(name="Käsekuchen", category=cake, is_sellable=True)
    ProductionDayProductFactory(product=planned)
    page = ContentPageFactory(
        parent=shop_page, content=[assortment(only_planned_products=True)]
    )

    assert get_assortment_categories(client, page) == [("Brot", True, ["Roggenbrot"])]


def test_assortment_without_products_renders_nothing(client, shop_page):
    page = ContentPageFactory(parent=shop_page, content=[assortment()])

    html = BeautifulSoup(client.get(page.url).content, "html.parser")

    assert html.select(".product-assortment") == []


def test_two_assortments_on_one_page_get_different_collapse_ids(client, shop_page):
    bread = Category.add_root(name="Brot", slug="brot")
    ProductFactory(name="Roggenbrot", category=bread, is_sellable=True)
    page = ContentPageFactory(parent=shop_page, content=[assortment(), assortment()])

    html = BeautifulSoup(client.get(page.url).content, "html.parser")

    ids = [c["id"] for c in html.select(".product-assortment .accordion-collapse")]
    assert len(ids) == 2, "expected one category per assortment block"
    assert ids[0] != ids[1]
