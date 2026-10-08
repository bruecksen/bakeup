from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.client import TenantClient

from bakeup.shop.models import ProductionDay, ProductionDayProduct
from bakeup.users.models import User
from bakeup.workshop.models import ProductHierarchy
from bakeup.workshop.tests.factories import ProductFactory, add
from bakeup.workshop.tests.test_models import RecipeTestCase


class RecipeViewTestCase(RecipeTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="baker", email="baker@example.com", password="x", is_staff=True
        )
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.user)

    def url(self, name, pk=None):
        return reverse(f"workshop:{name}", kwargs={"pk": pk or self.bread.pk})

    def detail(self, **params):
        response = self.client.get(self.url("product-detail"), params)
        self.assertEqual(response.status_code, 200)
        return response

    def set_percent_mode(self):
        self.client.post(self.url("product-recipe-mode"), {"mode": "percent"})


class ProductDetailViewTest(RecipeViewTestCase):
    def test_gram_mode(self):
        response = self.detail()
        self.assertFalse(response.context["percent_mode"])
        self.assertEqual(
            [row.pk for row in response.context["ingredients"]],
            [
                self.rows[name].pk
                for name in ["wheat", "water", "sourdough", "rye", "flour", "salt"]
            ],
        )
        initial = response.context["key_figures_form"].initial
        self.assertEqual(initial["dough_yield"], 144)
        self.assertEqual(initial["salt"], "1,5")
        self.assertEqual(initial["pre_ferment"], "13,6")
        self.assertEqual(initial["fermentation_loss"], "15,4")
        self.assertEqual(initial["total_dough_weight"], "1182")
        self.assertEqual(initial["wheat"], self.bread.get_wheats())
        self.assertContains(response, "Rye flour")
        self.assertContains(response, "Starter")

    def test_percent_mode(self):
        self.set_percent_mode()
        response = self.detail()
        self.assertTrue(response.context["percent_mode"])
        self.assertEqual(
            response.context["flour_pks"],
            [self.rows["wheat"].pk, self.rows["flour"].pk, self.rows["rye"].pk],
        )
        self.assertEqual(response.context["main_flour_pk"], self.rows["wheat"].pk)
        self.assertContains(response, "810 g = 100 %")

    def test_main_flour(self):
        self.set_percent_mode()
        self.client.post(
            self.url("product-main-flour"), {"hierarchy": self.rows["rye"].pk}
        )
        self.assertEqual(self.detail().context["main_flour_pk"], self.rows["rye"].pk)


class ProductDetailQueryTest(RecipeViewTestCase):
    def count_queries(self):
        with CaptureQueriesContext(connection) as queries:
            self.detail()
        return len(queries)

    def grow_recipe(self):
        # More rows on every level and a fourth level.
        poolish = ProductFactory(
            name="Poolish",
            category=self.categories["pre-dough"],
            weight=200,
            is_composable=True,
        )
        add(poolish, self.products["wheat"], 100)
        add(poolish, self.products["water"], 100)
        add(self.products["starter"], poolish, 5)
        add(self.products["sourdough"], self.products["salt"], 2)
        add(self.bread, poolish, 200)
        for name in ["Seeds", "Oil", "Malt"]:
            add(
                self.bread,
                ProductFactory(name=name, category=self.categories["ingredients"]),
                10,
            )

    def assert_constant_queries(self):
        self.detail()
        before = self.count_queries()
        self.grow_recipe()
        self.detail()
        self.assertEqual(self.count_queries(), before)

    def test_queries_dont_grow_with_recipe_in_gram_mode(self):
        self.assert_constant_queries()

    def test_queries_dont_grow_with_recipe_in_percent_mode(self):
        self.set_percent_mode()
        self.assert_constant_queries()


class RecipeEditViewTest(RecipeViewTestCase):
    def update_row(self, name, data):
        return self.client.post(
            reverse(
                "workshop:product-hierarchy-update", kwargs={"pk": self.rows[name].pk}
            ),
            data,
        )

    def test_update_row_in_gram(self):
        self.update_row("wheat", {"amount": "500"})
        self.assertAlmostEqual(self.row_weight("wheat"), 500)

    def test_update_row_in_percent_keeps_total_weight(self):
        self.update_row("wheat", {"amount": "50", "unit": "percent"})
        bread = self.reload()
        self.assertAlmostEqual(self.row_weight("wheat") / bread.total_weight_flour, 0.5)
        self.assertAlmostEqual(bread.total_weight, 1182)

    def test_update_row_in_percent_mode_keeps_flour(self):
        self.set_percent_mode()
        self.update_row("rye", {"amount": "20", "unit": "percent"})
        self.assertAlmostEqual(self.row_weight("rye"), 162)
        # The main flour (wheat, the largest) takes up the difference.
        self.assertAlmostEqual(self.row_weight("wheat"), 438)
        self.assertAlmostEqual(self.reload().total_weight_flour, 810)

    def test_add_ingredient_in_percent_mode(self):
        self.set_percent_mode()
        self.client.post(
            self.url("product-add-inline"),
            {
                "weight": "10",
                "ingredient": "new:Seeds",
                "category": self.categories["ingredients"].pk,
            },
        )
        row = ProductHierarchy.objects.get(parent=self.bread, child__name="Seeds")
        self.assertAlmostEqual(row.weight, 81)
        self.assertAlmostEqual(self.reload().total_weight_flour, 810)

    def test_dough_yield(self):
        self.client.post(self.url("product-dough-yield"), {"dough_yield": "170"})
        bread = self.reload()
        self.assertEqual(bread.get_dough_yield(), 170)
        self.assertAlmostEqual(bread.total_weight, 1182)

    def test_salt(self):
        self.set_percent_mode()
        self.client.post(self.url("product-salt"), {"salt": "2"})
        self.assertAlmostEqual(self.row_weight("salt"), 16.2)

    def test_pre_ferment(self):
        self.set_percent_mode()
        self.client.post(self.url("product-pre-ferment"), {"pre_ferment": "20"})
        bread = self.reload()
        self.assertAlmostEqual(bread.get_pre_ferment_ratio(), 20)
        self.assertAlmostEqual(bread.total_weight_flour, 810)

    def test_total_dough_weight(self):
        self.client.post(
            self.url("product-dough-weight"), {"total_dough_weight": "2364"}
        )
        self.assertAlmostEqual(self.reload().total_weight, 2364)

    def test_normalize(self):
        self.client.post(self.url("product-normalize"), {"fermentation_loss": "10"})
        self.assertAlmostEqual(self.reload().get_fermentation_loss(), 10, places=1)


class ShopProductionDayTest(RecipeViewTestCase):
    def setUp(self):
        super().setUp()
        self.production_day = ProductionDay.objects.create(
            day_of_sale=timezone.now().date() + timedelta(days=3)
        )
        self.offer(self.bread)

    def offer(self, product):
        ProductionDayProduct.objects.create(
            production_day=self.production_day,
            product=product,
            max_quantity=10,
            is_published=True,
        )

    def shop(self):
        response = TenantClient(self.tenant).get(
            reverse(
                "shop:shop-production-day",
                kwargs={"production_day": self.production_day.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        return response

    def recipe_queries(self):
        with CaptureQueriesContext(connection) as queries:
            self.shop()
        return [
            query["sql"]
            for query in queries
            if "workshop_producthierarchy" in query["sql"]
            or "workshop_productprice" in query["sql"]
        ]

    def test_recipe_queries_dont_grow_with_products(self):
        before = len(self.recipe_queries())
        for name in ["Rye bread", "Wheat bread"]:
            bread = ProductFactory(
                name=name, category=self.categories["bread"], is_sellable=True
            )
            add(bread, self.products["sourdough"], 300)
            add(bread, self.products["wheat"], 500)
            self.offer(bread)
        self.assertEqual(len(self.recipe_queries()), before)

    def test_product_card_lists_ingredients(self):
        response = self.shop()
        self.assertContains(
            response, "Wheat flour, Water, Rye flour, Flour, Salt", html=False
        )
