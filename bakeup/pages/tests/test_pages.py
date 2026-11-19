import pytest

from bakeup.pages.tests.factories import BlockReferencePageFactory, ContentPageFactory
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


def heading(title):
    return {
        "type": "text",
        "value": {"text": "<h2>{}</h2><p>Text</p>".format(title), "alignment": "start"},
    }


def test_block_reference_page_sections_get_anchors_from_their_headings(shop_page):
    page = BlockReferencePageFactory(
        parent=shop_page,
        title="Bausteine",
        content=[
            INTRO,
            heading("FAQ in einer Spalte (1|2)"),
            {"type": "hr", "value": {}},
            heading("Abstand &amp; <b>Größe</b>"),
            heading("FAQ in einer Spalte (1|2)"),
        ],
    )

    sections = [
        (section["anchor"], section["title"], [b.block_type for b in section["blocks"]])
        for section in page.get_sections()
    ]

    assert sections == [
        ("", "", ["text"]),
        (
            "baustein-faq-in-einer-spalte-12",
            "FAQ in einer Spalte (1|2)",
            ["text", "hr"],
        ),
        ("baustein-abstand-groesse", "Abstand & Größe", ["text"]),
        ("baustein-faq-in-einer-spalte-12-2", "FAQ in einer Spalte (1|2)", ["text"]),
    ]


def test_staff_user_can_jump_to_a_section_of_the_block_reference_page(
    client, shop_page
):
    page = BlockReferencePageFactory(
        parent=shop_page, title="Bausteine", content=[INTRO, heading("Schritte")]
    )
    client.force_login(UserFactory(is_staff=True))

    response = client.get(page.url)

    html = response.content.decode()
    assert '<a href="#baustein-schritte">Schritte</a>' in html
    assert '<section id="baustein-schritte"' in html
