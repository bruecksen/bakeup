import pytest
from wagtail.models import Site

from bakeup.conftest import TEST_DOMAIN
from bakeup.pages.tests.factories import ShopPageFactory


@pytest.fixture
def shop_page(tenant_db):
    page = ShopPageFactory(title="Shop", slug="shop")
    Site.objects.create(
        hostname=TEST_DOMAIN, root_page=page, is_default_site=False, port=80
    )
    return page
