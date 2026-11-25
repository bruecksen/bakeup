# The shop views render the base template, which needs a Wagtail site.
from bakeup.pages.tests.conftest import shop_page  # noqa: F401

# The abo tests go through the staff views of the workshop as well.
from bakeup.workshop.tests.conftest import (  # noqa: F401
    abo_products,
    production_day_form_data,
    sellable_products,
    staff_user,
)
