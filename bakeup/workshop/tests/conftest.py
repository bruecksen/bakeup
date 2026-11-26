import pytest

from bakeup.users.tests.factories import UserFactory
from bakeup.workshop.models import ProductionPlan
from bakeup.workshop.tests.factories import (
    ProductFactory,
    ProductionDayFactory,
    ProductionDayProductFactory,
    add,
    create_recipe,
)


@pytest.fixture
def staff_user(tenant_db):
    return UserFactory(username="baker", is_staff=True)


@pytest.fixture
def sellable_products(tenant_db):
    # Three sellable products with a recipe each, a product without a recipe
    # gets no production plan.
    categories, products, _rows = create_recipe()
    sellable = {"Bread": products["bread"]}
    for name in ["Brötchen", "Baguette"]:
        sellable[name] = ProductFactory(
            name=name, category=categories["bread"], weight=100, is_sellable=True
        )
        add(sellable[name], products["wheat"], 80)
    return sellable


@pytest.fixture
def planned_production_day(sellable_products):
    # A day selling Bread and Brötchen, with a planned plan for each.
    production_day = ProductionDayFactory()
    for name in ["Bread", "Brötchen"]:
        ProductionDayProductFactory(
            production_day=production_day, product=sellable_products[name]
        )
    production_day.create_or_update_production_plans(
        state=ProductionPlan.State.PLANNED, create_max_quantity=True
    )
    return production_day


@pytest.fixture
def abo_products(sellable_products):
    # Bread and Brötchen can be subscribed to, Baguette cannot.
    for name in ["Bread", "Brötchen"]:
        sellable_products[name].is_recurring = True
        sellable_products[name].save(update_fields=["is_recurring"])
    return sellable_products


@pytest.fixture
def production_day_form_data():
    """
    The POST data of the production day form. A row is a dict with the
    product, `id` for an existing row, and optionally `is_published`, `DELETE`
    and `max_quantity`.
    """

    def build(day_of_sale, rows, **fields):
        data = {
            "day_of_sale": day_of_sale.isoformat(),
            "form-TOTAL_FORMS": len(rows),
            "form-INITIAL_FORMS": len([row for row in rows if "id" in row]),
            **fields,
        }
        for index, row in enumerate(rows):
            data[f"form-{index}-product"] = row["product"].pk
            data[f"form-{index}-max_quantity"] = row.get("max_quantity", 10)
            if "id" in row:
                data[f"form-{index}-id"] = row["id"]
            # Unticked checkboxes are not posted.
            for checkbox in ["is_published", "DELETE"]:
                if row.get(checkbox):
                    data[f"form-{index}-{checkbox}"] = "on"
        return data

    return build


@pytest.fixture
def bread_plan(planned_production_day):
    # The main dough of 10 breads, the last step of the Bread card:
    # sourdough 2200 g, wheat 4000 g, flour 1000 g, rye 2000 g, water 2500 g
    # and salt 120 g.
    return ProductionPlan.objects.get(
        production_day=planned_production_day,
        parent_plan=None,
        product__product_template__name="Bread",
    )
