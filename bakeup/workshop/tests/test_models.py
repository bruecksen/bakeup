from decimal import Decimal

from django_tenants.test.cases import FastTenantTestCase

from bakeup.core.models import UOM
from bakeup.workshop.models import Category, Product, ProductHierarchy
from bakeup.workshop.templatetags.workshop_tags import clever_rounding
from bakeup.workshop.tests.factories import ProductFactory, add, create_recipe


class RecipeTestCase(FastTenantTestCase):
    def setUp(self):
        super().setUp()
        self.categories, self.products, self.rows = create_recipe()
        self.bread = self.products["bread"]

    def reload(self, product=None):
        return Product.objects.get(pk=(product or self.bread).pk)

    def row_weight(self, name):
        return ProductHierarchy.objects.get(pk=self.rows[name].pk).weight

    def quantities(self):
        return dict(ProductHierarchy.objects.values_list("pk", "quantity"))

    def weight_by(self, slug, product=None):
        return Product.calculate_total_weight_by_category(
            product or self.reload(), self.categories[slug]
        )


class RecipeCalculationTest(RecipeTestCase):
    def test_total_weight(self):
        self.assertAlmostEqual(self.bread.total_weight, 1182)
        self.assertAlmostEqual(Product.calculate_total_weight(self.bread), 1182)
        self.assertAlmostEqual(Product.calculate_total_weight(self.bread, 2), 2364)
        self.assertAlmostEqual(self.products["sourdough"].total_weight, 220)

    def test_total_weight_without_recipe_is_own_weight(self):
        self.assertEqual(self.products["wheat"].total_weight, 1000)

    def test_total_weight_by_category(self):
        self.assertAlmostEqual(self.weight_by("flour"), 810)
        self.assertAlmostEqual(self.weight_by("rye"), 310)
        self.assertAlmostEqual(self.weight_by("wheat"), 400)
        self.assertAlmostEqual(self.weight_by("liquids"), 360)
        self.assertAlmostEqual(self.weight_by("salt"), 12)
        # A row of the category counts with its whole weight, no recursion.
        self.assertAlmostEqual(self.weight_by("starter"), 20)
        self.assertAlmostEqual(self.weight_by("flour", self.products["sourdough"]), 110)
        self.assertAlmostEqual(
            Product.calculate_total_weight_by_category(
                self.bread, self.categories["flour"], 2
            ),
            1620,
        )

    def test_total_weight_by_category_and_parent(self):
        flour = self.categories["flour"]
        self.assertAlmostEqual(
            Product.calculate_total_weight_by_category_and_parent(
                self.bread, flour, 1, self.categories["pre-dough"]
            ),
            110,
        )
        self.assertAlmostEqual(
            Product.calculate_total_weight_by_category_and_parent(self.bread, flour),
            810,
        )

    def test_total_weight_by_ingredient(self):
        self.assertAlmostEqual(
            Product.calculate_total_weight_by_ingredient(
                self.bread, self.products["rye"]
            ),
            310,
        )
        self.assertAlmostEqual(
            Product.calculate_total_weight_by_ingredient(
                self.bread, self.products["water"]
            ),
            360,
        )

    def test_key_figures(self):
        self.assertAlmostEqual(self.bread.total_weight_flour, 810)
        self.assertEqual(self.bread.get_dough_yield(), 144)
        self.assertEqual(self.bread.get_salt_ratio(), 1.48)
        self.assertEqual(self.bread.get_pre_ferment_ratio(), 13.58)
        self.assertEqual(self.bread.get_starter_ratio(), 10)
        self.assertAlmostEqual(self.bread.get_fermentation_loss(), 15.4)
        self.assertFalse(self.bread.is_normalized)

    def test_wheats(self):
        self.assertEqual(
            self.bread.get_wheats(),
            "Rye ({}%)\nWheat ({}%)".format(
                clever_rounding(310 / 810 * 100), clever_rounding(400 / 810 * 100)
            ),
        )

    def test_key_figures_without_categories(self):
        Category.objects.filter(slug__in=["flour", "liquids", "salt"]).update(
            slug="other"
        )
        self.assertIsNone(self.bread.total_weight_flour)
        self.assertIsNone(self.bread.get_dough_yield())
        self.assertIsNone(self.bread.get_salt_ratio())
        self.assertIsNone(self.bread.get_pre_ferment_ratio())
        self.assertIsNone(self.bread.get_wheats())
        self.assertEqual(self.bread.get_flour_children(), [])

    def test_flour_children(self):
        self.assertEqual(
            [row.pk for row in self.bread.get_flour_children()],
            [self.rows["wheat"].pk, self.rows["flour"].pk, self.rows["rye"].pk],
        )

    def test_ingredient_list(self):
        self.assertEqual(
            [
                (item["product"].pk, item["quantity"])
                for item in self.bread.get_ingredient_list()
            ],
            [
                (self.rows[name].child_id, self.rows[name].quantity)
                for name in ["sourdough", "wheat", "flour", "rye", "water", "salt"]
            ],
        )

    def test_full_ingredient_list(self):
        ingredients = self.bread.get_full_ingredient_list()
        self.assertEqual(
            [product.name for product, weight in ingredients],
            ["Wheat flour", "Water", "Rye flour", "Flour", "Salt"],
        )
        for (product, weight), expected in zip(ingredients, [400, 360, 310, 100, 12]):
            self.assertAlmostEqual(weight, expected)
        self.assertEqual(self.products["wheat"].get_full_ingredient_list(), [])

    def test_hierarchy_is_leaf_and_weight(self):
        self.assertTrue(self.rows["wheat"].is_leaf)
        self.assertFalse(self.rows["sourdough"].is_leaf)
        self.assertAlmostEqual(self.rows["water"].weight, 250)
        self.assertAlmostEqual(self.rows["sourdough"].weight, 220)
        weightless = ProductFactory(weight=0)
        row = ProductHierarchy.objects.create(
            parent=self.bread, child=weightless, quantity=1
        )
        self.assertEqual(row.weight, "-")

    def test_weight_in_base_unit(self):
        gram = UOM.objects.create(name="Gram", abbreviation="g")
        kilogram = UOM.objects.create(
            name="Kilogram", abbreviation="kg", base_unit=gram, conversion_factor=1000
        )
        seeds = ProductFactory(
            name="Seeds",
            category=self.categories["ingredients"],
            weight=0.05,
            uom=kilogram,
        )
        self.assertAlmostEqual(seeds.weight_in_base_unit, 50)
        row = add(self.bread, seeds, 50)
        self.assertAlmostEqual(row.quantity, 1)
        self.assertAlmostEqual(self.reload().total_weight, 1232)

    def test_duplicate(self):
        copy = Product.duplicate(self.reload())
        self.assertNotEqual(copy.pk, self.bread.pk)
        self.assertEqual(copy.product_template_id, self.bread.pk)
        self.assertAlmostEqual(copy.total_weight, 1182)
        self.assertAlmostEqual(copy.total_weight_flour, 810)
        sourdough_copy = copy.parents.get(child__name="Sourdough").child
        self.assertNotEqual(sourdough_copy.pk, self.products["sourdough"].pk)
        self.assertEqual(
            sourdough_copy.product_template_id, self.products["sourdough"].pk
        )


class RecipeTreeTest(RecipeTestCase):
    def key_figures(self, bread):
        return [
            bread.total_weight,
            bread.total_weight_flour,
            bread.get_dough_yield(),
            bread.get_salt_ratio(),
            bread.get_pre_ferment_ratio(),
            bread.get_fermentation_loss(),
            [row.pk for row in bread.get_flour_children()],
            [row.pk for row in bread.get_children_by_weight()],
            [(p.pk, w) for p, w in bread.get_full_ingredient_list()],
        ]

    def test_loaded_tree_gives_same_figures(self):
        self.assertEqual(
            self.key_figures(self.reload().load_recipe_tree()),
            self.key_figures(self.reload()),
        )

    def test_load_recipe_tree_queries_once_per_level(self):
        bread = self.reload()
        # bread, its rows, the rows of the sourdough; the starter's ingredients
        # are already loaded as rows of the bread.
        with self.assertNumQueries(3):
            bread.load_recipe_tree()
        with self.assertNumQueries(0):
            for row in bread.parents.all():
                row.is_leaf, row.weight, row.child.category, row.child.uom
            bread.get_full_ingredient_list()
            bread.get_children_by_weight()

    def test_key_figures_query_only_categories(self):
        bread = self.reload().load_recipe_tree()
        self.key_figures(bread)
        bread.get_wheats()
        # Only the flour types of get_wheats() are queried again.
        with self.assertNumQueries(1):
            self.key_figures(bread)
            bread.get_wheats()

    def test_children_by_weight(self):
        self.assertEqual(
            [row.pk for row in self.reload().get_children_by_weight()],
            list(self.bread.parents.with_weights().values_list("pk", flat=True)),
        )

    def test_mutators_clear_loaded_tree(self):
        bread = self.reload().load_recipe_tree()
        self.assertAlmostEqual(bread.total_weight_flour, 810)
        bread.adjust_total_weight(2364)
        self.assertAlmostEqual(bread.total_weight_flour, 1620)
        bread.add_child(ProductFactory(category=self.categories["wheat"]), 0.1)
        self.assertAlmostEqual(bread.total_weight_flour, 1720)


class RecipeAdjustTest(RecipeTestCase):
    def assert_unchanged(self, quantities):
        self.assertEqual(self.quantities(), quantities)

    def test_normalize(self):
        self.reload().normalize(Decimal("10"))
        bread = self.reload()
        self.assertAlmostEqual(bread.total_weight, 1182 * (1 - 0.154) / 0.9)
        self.assertAlmostEqual(bread.get_fermentation_loss(), 10, places=1)

    def test_dough_yield_keep_total_weight(self):
        self.assertTrue(self.reload().adjust_dough_yield(170))
        bread = self.reload()
        self.assertEqual(bread.get_dough_yield(), 170)
        self.assertAlmostEqual(bread.total_weight, 1182)
        self.assertAlmostEqual(
            self.weight_by("rye") / bread.total_weight_flour, 310 / 810
        )
        self.assertAlmostEqual(bread.get_salt_ratio(), 1.48)

    def test_dough_yield_keep_flour(self):
        self.assertTrue(self.reload().adjust_dough_yield(170, keep_total_weight=False))
        bread = self.reload()
        self.assertAlmostEqual(bread.total_weight_flour, 810)
        self.assertAlmostEqual(self.row_weight("water"), 457)
        self.assertAlmostEqual(bread.total_weight, 1389)

    def test_dough_yield_not_reachable(self):
        quantities = self.quantities()
        self.assertFalse(self.reload().adjust_dough_yield(110))
        self.assert_unchanged(quantities)

    def test_salt_ratio(self):
        self.assertTrue(self.reload().adjust_salt_ratio(Decimal("2.00"), False))
        self.assertAlmostEqual(self.row_weight("salt"), 16.2)
        self.assertAlmostEqual(self.reload().total_weight_flour, 810)

        self.assertTrue(self.reload().adjust_salt_ratio(Decimal("1.50")))
        bread = self.reload()
        self.assertEqual(bread.get_salt_ratio(), 1.5)
        self.assertAlmostEqual(bread.total_weight, 1182 - 12 + 16.2)

    def test_total_weight(self):
        self.assertTrue(self.reload().adjust_total_weight(Decimal("2364")))
        bread = self.reload()
        self.assertAlmostEqual(bread.total_weight, 2364)
        self.assertAlmostEqual(bread.total_weight_flour, 1620)
        self.assertEqual(bread.get_dough_yield(), 144)
        quantities = self.quantities()
        self.assertFalse(self.reload().adjust_total_weight(0))
        self.assert_unchanged(quantities)

    def test_child_ratio_keep_total_weight(self):
        bread = self.reload()
        self.assertTrue(bread.adjust_child_ratio(self.rows["wheat"], 50))
        bread = self.reload()
        self.assertAlmostEqual(self.row_weight("wheat") / bread.total_weight_flour, 0.5)
        self.assertAlmostEqual(bread.total_weight, 1182)

    def test_child_ratio_keep_flour_with_balancing(self):
        bread = self.reload()
        self.assertTrue(
            bread.adjust_child_ratio(
                ProductHierarchy.objects.get(pk=self.rows["wheat"].pk),
                50,
                keep_total_weight=False,
                balancing=self.rows["flour"],
            )
        )
        self.assertAlmostEqual(self.row_weight("wheat"), 405)
        self.assertAlmostEqual(self.row_weight("flour"), 95)
        self.assertAlmostEqual(self.row_weight("rye"), 200)
        self.assertAlmostEqual(self.reload().total_weight_flour, 810)

    def test_child_ratio_keep_flour_without_balancing(self):
        bread = self.reload()
        self.assertTrue(
            bread.adjust_child_ratio(self.rows["wheat"], 50, keep_total_weight=False)
        )
        self.assertAlmostEqual(self.row_weight("wheat"), 405)
        self.assertAlmostEqual(self.row_weight("flour"), 100 * 295 / 300)
        self.assertAlmostEqual(self.row_weight("rye"), 200 * 295 / 300)
        self.assertAlmostEqual(self.reload().total_weight_flour, 810)

    def test_child_ratio_of_pre_dough(self):
        bread = self.reload()
        self.assertTrue(
            bread.adjust_child_ratio(
                self.rows["sourdough"], 40, keep_total_weight=False
            )
        )
        self.assertAlmostEqual(self.row_weight("sourdough"), 324)
        self.assertAlmostEqual(self.row_weight("wheat"), 400 * 648 / 700)
        self.assertAlmostEqual(self.reload().total_weight_flour, 810)

    def test_child_ratio_not_reachable(self):
        quantities = self.quantities()
        self.assertFalse(self.reload().adjust_child_ratio(self.rows["wheat"], 0))
        self.assertFalse(self.reload().adjust_child_ratio(self.rows["wheat"], 100))
        self.assert_unchanged(quantities)

    def test_pre_ferment_keep_flour(self):
        self.assertTrue(
            self.reload().adjust_pre_ferment_ratio(
                Decimal("20"), keep_total_weight=False
            )
        )
        bread = self.reload()
        self.assertAlmostEqual(bread.get_pre_ferment_ratio(), 20)
        self.assertAlmostEqual(self.row_weight("sourdough"), 324)
        self.assertAlmostEqual(bread.total_weight_flour, 810)
        self.assertAlmostEqual(self.weight_by("rye"), 310)
        self.assertAlmostEqual(self.weight_by("wheat"), 400)
        self.assertAlmostEqual(self.weight_by("liquids"), 360)
        self.assertAlmostEqual(self.weight_by("salt"), 12)

    def test_pre_ferment_keep_total_weight(self):
        self.assertTrue(self.reload().adjust_pre_ferment_ratio(Decimal("20")))
        bread = self.reload()
        self.assertAlmostEqual(bread.get_pre_ferment_ratio(), 20)
        self.assertAlmostEqual(bread.total_weight, 1182)
        self.assertEqual(bread.get_dough_yield(), 144)
        self.assertEqual(bread.get_salt_ratio(), 1.48)

    def test_pre_ferment_without_pre_dough(self):
        quantities = self.quantities()
        self.assertFalse(
            self.reload(self.products["sourdough"]).adjust_pre_ferment_ratio(20)
        )
        self.assert_unchanged(quantities)
