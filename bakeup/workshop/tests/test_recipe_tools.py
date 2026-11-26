import pytest

from bakeup.workshop.models import Product
from bakeup.workshop.recipe_tools import heat_capacity, water_temperature
from bakeup.workshop.tests.factories import ProductFactory, create_recipe

# 1000 g flour (1.8) and 20 g salt (0.9), the water is 600 g (4.19):
# sum of m * c = 600 * 4.19 + 1000 * 1.8 + 20 * 0.9 = 2514 + 1800 + 18 = 4332


def flour_and_salt(flour_temperature=20, salt_temperature=20):
    return [(1000, 1.8, flour_temperature), (20, 0.9, salt_temperature)]


def test_water_temperature_matches_the_hand_computed_example():
    # (26 * 4332 - (1800 * 20 + 18 * 20)) / 2514 = (112632 - 36360) / 2514
    result = water_temperature(26, 0, 600, flour_and_salt())

    assert result == pytest.approx(76272 / 2514)
    assert round(result, 2) == 30.34


@pytest.mark.parametrize(
    "dough, warming, water, others, expected",
    [
        # Everything as warm as the dough shall be, so is the water.
        pytest.param(20, 0, 600, flour_and_salt(), 20, id="all at 20"),
        # (112632 - (1800 * 10 + 18 * 20)) / 2514 = 94272 / 2514
        pytest.param(26, 0, 600, flour_and_salt(10), 94272 / 2514, id="cold flour"),
        # ((26 - 2) * 4332 - 36360) / 2514 = 67608 / 2514
        pytest.param(26, 2, 600, flour_and_salt(), 67608 / 2514, id="mixer warming"),
        # Only water, it is the dough.
        pytest.param(26, 0, 600, [], 26, id="only water"),
        pytest.param(26, 0, 0, flour_and_salt(), None, id="no water"),
    ],
)
def test_water_temperature(dough, warming, water, others, expected):
    result = water_temperature(dough, warming, water, others)

    assert result == (expected if expected is None else pytest.approx(expected))


@pytest.mark.parametrize(
    "product, expected",
    [
        # The category itself.
        ("salt", 0.9),
        # Rye is a sub category of flour.
        ("rye", 1.8),
        # Without a category the fallback.
        ("uncategorized", 2.0),
        # 110 g rye and 110 g water, with the starter:
        # (110 * 1.8 + 110 * 4.19) / 220
        ("sourdough", 2.995),
    ],
)
def test_heat_capacity(tenant_db, product, expected):
    _categories, products, _rows = create_recipe()
    products["uncategorized"] = ProductFactory(name="Raisins", category=None)

    assert heat_capacity(products[product]) == pytest.approx(expected)


def test_plan_copy_of_a_recipe_keeps_its_dough_temperature_and_mixer_warming(
    tenant_db,
):
    _categories, products, _rows = create_recipe()
    bread = products["bread"]
    bread.dough_temperature = 24.5
    bread.mixer_warming = 3
    bread.save()

    copy = Product.duplicate(Product.objects.get(pk=bread.pk))

    copy.refresh_from_db()
    assert copy.pk != bread.pk
    assert (copy.dough_temperature, copy.mixer_warming) == (24.5, 3)
