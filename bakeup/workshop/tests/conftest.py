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
