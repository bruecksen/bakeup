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
