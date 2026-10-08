from factory import Sequence
from factory.django import DjangoModelFactory

from bakeup.workshop.models import Category, Product, ProductHierarchy


class ProductFactory(DjangoModelFactory):
    name = Sequence(lambda n: f"Product {n}")
    weight = 1000

    class Meta:
        model = Product


class ProductHierarchyFactory(DjangoModelFactory):
    class Meta:
        model = ProductHierarchy


def create_categories():
    # The slugs the recipe calculations look up, in the tree of
    # bakeup/workshop/fixtures/demo_categories.json.
    ingredients = Category.add_root(name="Ingredients", slug="ingredients")
    flour = ingredients.add_child(name="Flour", slug="flour")
    categories = {
        "ingredients": ingredients,
        "flour": flour,
        "rye": flour.add_child(name="Rye", slug="rye"),
        "wheat": flour.add_child(name="Wheat", slug="wheat"),
        "liquids": ingredients.add_child(name="Liquids", slug="liquids"),
        "salt": ingredients.add_child(name="Salt", slug="salt"),
        "starter": ingredients.add_child(name="Starter", slug="starter"),
    }
    dough = Category.add_root(name="Dough", slug="dough")
    categories["dough"] = dough
    categories["pre-dough"] = dough.add_child(name="Pre dough", slug="pre-dough")
    categories["main-dough"] = dough.add_child(name="Main dough", slug="main-dough")
    categories["bread"] = Category.add_root(name="Bread", slug="bread")
    return {slug: Category.objects.get(pk=c.pk) for slug, c in categories.items()}


def add(parent, child, grams):
    return ProductHierarchyFactory(
        parent=parent, child=child, quantity=grams / child.weight_in_base_unit
    )


def create_recipe():
    """A bread with a sourdough that contains a starter (three levels).

    bread (1000 g loaf)
      sourdough 220 g: rye 100 g, water 100 g, starter 20 g (rye 10 g, water 10 g)
      wheat 400 g, flour 100 g, rye 200 g, water 250 g, salt 12 g

    Totals: flour 810 g (rye 310, wheat 400, plain 100), water 360 g,
    salt 12 g, dough 1182 g.
    """
    c = create_categories()
    rye = ProductFactory(name="Rye flour", category=c["rye"])
    wheat = ProductFactory(name="Wheat flour", category=c["wheat"])
    flour = ProductFactory(name="Flour", category=c["flour"])
    water = ProductFactory(name="Water", category=c["liquids"])
    salt = ProductFactory(name="Salt", category=c["salt"])
    starter = ProductFactory(name="Starter", category=c["starter"], weight=20)
    add(starter, rye, 10)
    add(starter, water, 10)
    sourdough = ProductFactory(name="Sourdough", category=c["pre-dough"], weight=220)
    rows = {
        "sourdough_rye": add(sourdough, rye, 100),
        "sourdough_water": add(sourdough, water, 100),
        "sourdough_starter": add(sourdough, starter, 20),
    }
    bread = ProductFactory(
        name="Bread",
        category=c["bread"],
        weight=1000,
        is_sellable=True,
    )
    rows.update(
        {
            "sourdough": add(bread, sourdough, 220),
            "wheat": add(bread, wheat, 400),
            "flour": add(bread, flour, 100),
            "rye": add(bread, rye, 200),
            "water": add(bread, water, 250),
            "salt": add(bread, salt, 12),
        }
    )
    products = {
        "bread": bread,
        "sourdough": sourdough,
        "starter": starter,
        "rye": rye,
        "wheat": wheat,
        "flour": flour,
        "water": water,
        "salt": salt,
    }
    return c, products, rows
