import json
from datetime import timedelta
from io import StringIO
from urllib.parse import quote

from django.core.management import call_command
from django.db import connection
from django.db.models import Sum
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation
from django_tenants.test.client import TenantClient

from bakeup.contrib.models import Note
from bakeup.shop.models import (
    Customer,
    CustomerOrder,
    CustomerOrderPosition,
    PointOfSale,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.users.models import User
from bakeup.workshop.models import (
    Instruction,
    Product,
    ProductHierarchy,
    ProductionPlan,
    ProductMapping,
    ReminderMessage,
    VatRate,
)
from bakeup.workshop.templatetags.workshop_tags import clever_unit
from bakeup.workshop.tests.factories import ProductFactory, add
from bakeup.workshop.tests.test_models import NumberCircleTestCase, RecipeTestCase


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

    def test_recipe_without_flour_stays_in_gram(self):
        brine = ProductFactory(name="Brine")
        add(brine, self.products["water"], 100)
        add(brine, self.products["salt"], 10)
        self.set_percent_mode()
        response = self.client.get(self.url("product-detail", brine.pk))
        self.assertFalse(response.context["percent_mode"])
        self.assertNotContains(response, "(None)")
        self.assertContains(response, 'value="percent" autocomplete="off" disabled')

    def test_main_flour(self):
        self.set_percent_mode()
        self.client.post(
            self.url("product-main-flour"), {"hierarchy": self.rows["rye"].pk}
        )
        self.assertEqual(self.detail().context["main_flour_pk"], self.rows["rye"].pk)


class ProductListViewTest(RecipeViewTestCase):
    def names(self, **params):
        response = self.client.get(reverse("workshop:product-list"), params)
        self.assertEqual(response.status_code, 200)
        return {row.record.name for row in response.context["table"].rows}

    def test_lists_ingredients_and_doughs(self):
        ingredients_and_doughs = {
            "Rye flour",
            "Wheat flour",
            "Flour",
            "Water",
            "Salt",
            "Starter",
            "Sourdough",
        }
        self.assertEqual(self.names(), ingredients_and_doughs)
        self.assertEqual(self.names(all=""), ingredients_and_doughs | {"Bread"})

    def test_add_from_recipes_is_sellable(self):
        response = self.client.get(reverse("workshop:product-add") + "?sellable")
        self.assertTrue(response.context["form"].initial["is_sellable"])
        response = self.client.get(reverse("workshop:product-add"))
        self.assertNotIn("is_sellable", response.context["form"].initial)

    def test_has_recipe(self):
        self.assertTrue(self.products["sourdough"].has_recipe)
        self.assertFalse(self.products["salt"].has_recipe)
        self.assertTrue(self.reload().load_recipe_tree().has_recipe)


class SidebarTest(RecipeViewTestCase):
    def assert_active(self, url, active_url):
        response = self.client.get(url)
        self.assertContains(
            response, f'aria-current="page" href="{active_url}"', count=1
        )

    def test_section_from_url(self):
        self.assert_active(reverse("workshop:workshop"), "/workshop/")
        self.assert_active(
            reverse("workshop:category-list"), reverse("workshop:category-list")
        )
        self.assert_active(reverse("users:update"), reverse("users:update"))

    def test_collapsed_from_the_cookie(self):
        url = reverse("workshop:workshop")
        self.assertNotContains(
            self.client.get(url),
            "sidebar col-auto px-2 bg-dark d-print-none is-collapsed",
        )
        self.client.cookies["sidebar_collapsed"] = "1"
        response = self.client.get(url)
        self.assertContains(
            response, "sidebar col-auto px-2 bg-dark d-print-none is-collapsed"
        )
        self.assertContains(
            response,
            'data-sidebar-collapse aria-controls="workshop-sidebar" aria-expanded="false"',
        )

    def test_product_pages_by_sellable(self):
        self.assert_active(self.url("product-detail"), reverse("workshop:recipe-list"))
        self.assert_active(
            self.url("product-detail", self.products["salt"].pk),
            reverse("workshop:product-list"),
        )
        self.assert_active(
            reverse("workshop:product-add") + "?sellable",
            reverse("workshop:recipe-list"),
        )


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

    def test_add_new_ingredient_gets_gram_uom(self):
        self.client.post(
            self.url("product-add-inline"),
            {
                "weight": "10",
                "ingredient": "new:Seeds",
                "category": self.categories["ingredients"].pk,
            },
        )
        self.assertEqual(Product.objects.get(name="Seeds").uom.abbreviation, "g")

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


class CheckoutPointOfSaleTest(RecipeViewTestCase):
    def setUp(self):
        super().setUp()
        self.production_day = ProductionDay.objects.create(
            day_of_sale=timezone.now().date() + timedelta(days=3)
        )
        ProductionDayProduct.objects.create(
            production_day=self.production_day,
            product=self.bread,
            max_quantity=10,
            is_published=True,
        )
        self.own = PointOfSale.objects.create(name="Depot Nord")
        self.other = PointOfSale.objects.create(name="TukTuk Café")
        self.customer = self.user.customer
        self.customer.point_of_sale = self.own
        self.customer.save()
        self.production_day.point_of_sales.set([self.other])

    def checkout(self):
        response = self.client.get(
            reverse(
                "shop:shop-production-day",
                kwargs={"production_day": self.production_day.pk},
            )
        )
        self.assertEqual(response.status_code, 200)
        return response

    def order(self, **data):
        self.client.post(
            reverse(
                "shop:customer-order-add",
                kwargs={"production_day": self.production_day.pk},
            ),
            {"create": "", f"product-{self.bread.pk}": 1, **data},
        )
        return CustomerOrder.objects.filter(
            production_day=self.production_day, customer=self.customer
        ).first()

    def test_asks_for_point_of_sale_when_own_is_unavailable(self):
        response = self.checkout()
        self.assertContains(response, "pos-hint")
        self.assertContains(response, '<option value="" selected disabled>')

    def test_preselects_own_point_of_sale_when_available(self):
        self.production_day.point_of_sales.add(self.own)
        response = self.checkout()
        self.assertNotContains(response, "pos-hint")
        self.assertContains(response, f'<option value="{self.own.pk}"  selected>')

    def test_order_needs_an_available_point_of_sale(self):
        self.assertIsNone(self.order())
        self.assertIsNone(self.order(point_of_sale=self.own.pk))
        self.assertEqual(
            self.order(point_of_sale=self.other.pk).point_of_sale, self.other
        )

    def test_order_keeps_its_point_of_sale_when_none_is_posted(self):
        self.order(point_of_sale=self.other.pk)
        self.customer.point_of_sale = None
        self.customer.save()
        self.assertEqual(self.order().point_of_sale, self.other)

    def test_internal_point_of_sale_is_not_offered(self):
        internal = PointOfSale.objects.create(name="Lieferung Café", is_internal=True)
        self.production_day.point_of_sales.add(self.own, internal)
        self.assertNotContains(self.checkout(), internal.name)
        self.assertEqual(self.order(point_of_sale=internal.pk), None)

    def test_internal_point_of_sale_is_offered_to_its_own_customer(self):
        internal = PointOfSale.objects.create(name="Lieferung Café", is_internal=True)
        self.production_day.point_of_sales.add(internal)
        self.customer.point_of_sale = internal
        self.customer.save()
        self.assertContains(
            self.checkout(), f'<option value="{internal.pk}"  selected>'
        )
        self.assertEqual(self.order().point_of_sale, internal)


class FirstOrderTest(RecipeViewTestCase):
    def setUp(self):
        super().setUp()
        today = timezone.now().date()
        self.first_day = ProductionDay.objects.create(day_of_sale=today)
        self.second_day = ProductionDay.objects.create(
            day_of_sale=today + timedelta(days=7)
        )
        self.depot = PointOfSale.objects.create(name="Depot Nord")
        self.regular = self.user.customer
        self.newcomer = User.objects.create_user(
            username="new", email="new@example.com", last_name="Neu"
        ).customer
        # The regular's later order is placed first: the production day
        # decides, not the time of ordering.
        self.order(self.regular, self.second_day)
        self.order(self.regular, self.first_day)
        self.order(self.newcomer, self.second_day)

    def order(self, customer, production_day):
        return CustomerOrder.objects.create(
            customer=customer, production_day=production_day, point_of_sale=self.depot
        )

    def first_orders(self, production_day):
        return {
            order.customer: order.is_first_order
            for order in CustomerOrder.objects.filter(
                production_day=production_day
            ).with_is_first_order()
        }

    def test_first_order_is_on_the_earliest_production_day(self):
        self.assertEqual(self.first_orders(self.first_day), {self.regular: True})
        self.assertEqual(
            self.first_orders(self.second_day),
            {self.regular: False, self.newcomer: True},
        )

    def test_order_without_customer_is_no_first_order(self):
        self.order(None, self.first_day)
        self.assertEqual(self.first_orders(self.first_day)[None], False)

    def test_first_order_date(self):
        without_order = User.objects.create_user(
            username="none", email="none@example.com"
        ).customer
        dates = {
            customer: customer.first_order_date
            for customer in Customer.objects.with_first_order_date()
        }
        self.assertEqual(dates[self.regular], self.first_day.day_of_sale)
        self.assertEqual(dates[self.newcomer], self.second_day.day_of_sale)
        self.assertIsNone(dates[without_order])

    def test_customer_export_has_first_order_date(self):
        response = self.client.get(
            reverse("workshop:customer-list"), {"_export": "csv"}
        )
        rows = response.content.decode().splitlines()
        row = next(row for row in rows if "new@example.com" in row)
        self.assertIn(self.second_day.day_of_sale.isoformat(), row)

    def test_customer_detail_shows_first_order_date(self):
        response = self.client.get(
            reverse("workshop:customer-detail", kwargs={"pk": self.newcomer.pk})
        )
        self.assertEqual(
            response.context["object"].first_order_date, self.second_day.day_of_sale
        )

    def test_delivery_bill_marks_first_orders(self):
        response = self.client.get(
            reverse("workshop:production-day-detail", kwargs={"pk": self.second_day.pk})
        )
        self.assertContains(response, "badge-first-order", count=1)

    def test_order_list_marks_first_orders(self):
        params = {"production_day": self.second_day.pk}
        response = self.client.get(reverse("workshop:order-list"), params)
        self.assertContains(response, "badge-first-order", count=1)
        response = self.client.get(
            reverse("workshop:order-list"), {**params, "_export": "csv"}
        )
        header, *rows = [
            row.split(",") for row in response.content.decode().splitlines()
        ]
        rows = [dict(zip(header, row)) for row in rows]
        self.assertEqual(
            {row["E-Mail"]: row["Erstbestellung"] for row in rows},
            {"baker@example.com": "", "new@example.com": "x"},
        )

    def test_production_day_export_marks_first_orders(self):
        response = self.client.get(
            reverse("workshop:production-day-export", kwargs={"pk": self.second_day.pk})
        )
        rows = [row.split(",") for row in response.content.decode().splitlines()]
        marks = {row[2]: row[-1] for row in rows if "@" in row[2]}
        self.assertEqual(marks, {"baker@example.com": "", "new@example.com": "x"})


class ProductionPlanDayViewTest(RecipeViewTestCase):
    def setUp(self):
        super().setUp()
        self.production_day = ProductionDay.objects.create(
            day_of_sale=timezone.now().date() + timedelta(days=3)
        )
        self.cake = ProductFactory(name="Cake", is_sellable=True)
        self.day_products = {
            product.pk: ProductionDayProduct.objects.create(
                production_day=self.production_day,
                product=product,
                max_quantity=10,
            )
            for product in [self.bread, self.cake]
        }
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )

    def day_url(self):
        return self.url("production-plan-production-day", self.production_day.pk)

    def cards(self):
        response = self.client.get(self.day_url())
        self.assertEqual(response.status_code, 200)
        return {
            card["root"].product.product_template: card
            for card in response.context["cards"]
        }

    def root(self, product=None):
        return ProductionPlan.objects.get(
            parent_plan=None, product__product_template=product or self.bread
        )

    def start(self):
        self.root().set_production()

    def sub_plan(self, name):
        return ProductionPlan.objects.get(
            production_day=self.production_day, product__name=name
        )

    def toggle(self, plan, row):
        return self.client.post(
            reverse(
                "workshop:production-plan-ingredient-toggle",
                kwargs={"pk": plan.pk, "row_pk": row.pk},
            )
        )

    def test_recipe_steps_are_ordered_deepest_first(self):
        card = self.cards()[self.bread]
        self.assertTrue(card["has_recipe"])
        self.assertEqual(
            [step["plan"].product.name for step in card["steps"]],
            ["Starter", "Sourdough", "Bread"],
        )
        sourdough = card["steps"][1]
        self.assertEqual(
            [row["row"].child.name for row in sourdough["rows"]],
            ["Rye flour", "Water", "Starter"],
        )
        self.assertAlmostEqual(sourdough["total"], 2200)
        bread = card["steps"][2]
        self.assertEqual(
            [row["row"].child.name for row in bread["rows"]],
            ["Wheat flour", "Water", "Sourdough", "Rye flour", "Flour", "Salt"],
        )
        self.assertAlmostEqual(card["piece_weight"], 1182)
        self.assertFalse(sourdough["show_checks"])

    def test_stages_and_references(self):
        card = self.cards()[self.bread]
        self.assertEqual(
            [
                (stage["number"], stage["depth"], len(stage["steps"]))
                for stage in card["stages"]
            ],
            [(1, 2, 1), (2, 1, 1), (3, 0, 1)],
        )
        self.assertEqual(
            [stage["label"] for stage in card["stages"][:2]], ["Starter", "Pre dough"]
        )
        refs = {
            row["row"].child.name: row["ref"]["stage"]
            for step in card["steps"]
            for row in step["rows"]
            if row["ref"]
        }
        self.assertEqual(refs, {"Starter": 1, "Sourdough": 2})

    def test_plan_keeps_a_copy_of_the_instructions(self):
        instruction = Instruction.objects.create(
            product=self.bread, instruction="Knead 10 minutes"
        )
        self.client.get(self.url("production-plan-update", self.root().pk))
        self.assertEqual(self.cards()[self.bread]["instructions"], "Knead 10 minutes")
        instruction.instruction = "Knead 5 minutes"
        instruction.save()
        self.assertEqual(self.cards()[self.bread]["instructions"], "Knead 10 minutes")

    def test_product_without_recipe_gets_no_plan(self):
        self.assertNotIn(self.cake, self.cards())
        self.assertFalse(
            ProductionPlan.objects.filter(product__product_template=self.cake).exists()
        )
        self.assertIsNone(
            ProductionDayProduct.objects.get(
                pk=self.day_products[self.cake.pk].pk
            ).production_plan
        )

    def test_plan_of_product_without_recipe_is_removed(self):
        # A plan from before products without a recipe were skipped.
        cake_plan = ProductionPlan.objects.create(
            production_day=self.production_day,
            product=Product.duplicate(self.cake),
            quantity=10,
            state=ProductionPlan.State.CANCELED,
        )
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
        self.assertFalse(ProductionPlan.objects.filter(pk=cake_plan.pk).exists())

    def create_plans_without_recipe(self, **options):
        call_command(
            "create_production_plans_without_recipe", stdout=StringIO(), **options
        )

    def test_command_plans_product_without_recipe(self):
        bread_plan = self.root()
        self.create_plans_without_recipe()
        cake_plan = self.root(self.cake)
        self.assertEqual(cake_plan.quantity, 10)
        self.assertTrue(cake_plan.is_planned)
        self.assertEqual(
            ProductionDayProduct.objects.get(
                pk=self.day_products[self.cake.pk].pk
            ).production_plan,
            cake_plan,
        )
        self.assertFalse(self.cards()[self.cake]["has_recipe"])
        self.assertEqual(self.root(), bread_plan)

    def test_command_starts_product_without_recipe(self):
        order = CustomerOrder.objects.create(
            production_day=self.production_day, address=""
        )
        position = CustomerOrderPosition.objects.create(
            order=order, product=self.cake, quantity=3
        )
        self.create_plans_without_recipe(
            day=self.production_day.day_of_sale, state="production"
        )
        cake_plan = self.root(self.cake)
        self.assertEqual(cake_plan.quantity, 3)
        self.assertTrue(cake_plan.is_production)
        position.refresh_from_db()
        self.assertEqual(position.production_plan, cake_plan)
        self.assertEqual(position.product, cake_plan.product)
        # The workshop keeps a started plan when the day is saved again.
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
        self.create_plans_without_recipe(state="production")
        self.assertEqual(self.root(self.cake), cake_plan)

    def test_command_sums_the_orders_of_the_day(self):
        other_day = ProductionDay.objects.create(
            day_of_sale=self.production_day.day_of_sale + timedelta(days=7)
        )
        ProductionDayProduct.objects.create(
            production_day=other_day, product=self.cake, max_quantity=10
        )
        for production_day, product, quantity in [
            (self.production_day, self.cake, 3),
            (self.production_day, self.cake, 4),
            (self.production_day, self.bread, 5),
            (other_day, self.cake, 6),
        ]:
            order = CustomerOrder.objects.create(
                production_day=production_day, address=""
            )
            CustomerOrderPosition.objects.create(
                order=order, product=product, quantity=quantity
            )
        day = self.production_day.day_of_sale
        self.create_plans_without_recipe(day=day, state="production")
        cake_plan = self.root(self.cake)
        self.assertEqual(cake_plan.quantity, 7)
        self.assertEqual(
            cake_plan.orders.aggregate(Sum("quantity"))["quantity__sum"], 7
        )
        self.assertFalse(other_day.production_plans.exists())
        self.assertTrue(self.root().is_planned)

    def test_started_plan_without_recipe_can_be_finished(self):
        order = CustomerOrder.objects.create(
            production_day=self.production_day, address=""
        )
        CustomerOrderPosition.objects.create(order=order, product=self.cake, quantity=3)
        self.create_plans_without_recipe(state="production")
        cake_plan = self.root(self.cake)
        day = {"production_day": self.production_day.pk}
        # Starting and finishing the whole day keeps the plan.
        self.client.get(reverse("workshop:production-plans-start", kwargs=day))
        self.assertTrue(self.root(self.cake).is_production)
        self.client.get(reverse("workshop:production-plans-finish", kwargs=day))
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
        cake_plan.refresh_from_db()
        self.assertTrue(cake_plan.is_produced)
        self.assertEqual(cake_plan.quantity, 3)
        self.assertTrue(order.is_locked)

    def test_started_plan_without_recipe_can_be_finished_on_its_own(self):
        self.create_plans_without_recipe(state="production")
        # Without orders the plan is canceled, there is nothing to finish.
        self.assertTrue(self.root(self.cake).is_canceled)
        order = CustomerOrder.objects.create(
            production_day=self.production_day, address=""
        )
        CustomerOrderPosition.objects.create(order=order, product=self.cake, quantity=3)
        self.create_plans_without_recipe(state="production")
        cake_plan = self.root(self.cake)
        self.client.get(self.url("production-plan-finish", cake_plan.pk))
        cake_plan.refresh_from_db()
        self.assertTrue(cake_plan.is_produced)

    def test_order_is_locked_without_plan_for_product_without_recipe(self):
        order = CustomerOrder.objects.create(
            production_day=self.production_day, address=""
        )
        CustomerOrderPosition.objects.create(
            order=order, product=self.bread, quantity=1, production_plan=self.root()
        )
        CustomerOrderPosition.objects.create(order=order, product=self.cake, quantity=1)
        self.assertFalse(order.is_locked)
        self.start()
        self.assertTrue(order.is_locked)

    def test_summary(self):
        response = self.client.get(self.day_url())
        summary = response.context["summary"]
        self.assertEqual(summary["products"], 1)
        self.assertEqual(summary["pieces"], 10)
        self.assertContains(response, 'id="production-summary"')

    def test_toggle_needs_production(self):
        plan = self.sub_plan("Sourdough")
        row = plan.product.parents.first()
        self.assertEqual(self.toggle(plan, row).status_code, 400)
        plan.refresh_from_db()
        self.assertEqual(plan.checked_ingredients, [])

    def test_toggle_ingredient(self):
        self.start()
        plan = self.sub_plan("Sourdough")
        row = plan.product.parents.first()
        response = self.toggle(plan, row)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="steps-{self.root().pk}"')
        self.assertContains(response, f'id="step-{self.sub_plan("Starter").pk}"')
        self.assertContains(response, 'hx-swap-oob="true"')
        plan.refresh_from_db()
        self.assertEqual(plan.checked_ingredients, [row.pk])
        card = self.cards()[self.bread]
        self.assertEqual((card["checked_count"], card["row_count"]), (1, 11))
        self.toggle(plan, row)
        plan.refresh_from_db()
        self.assertEqual(plan.checked_ingredients, [])

    def test_toggle_all_ingredients(self):
        self.start()
        plan = self.sub_plan("Sourdough")
        url = reverse(
            "workshop:production-plan-ingredients-toggle-all", kwargs={"pk": plan.pk}
        )
        self.toggle(plan, plan.product.parents.first())
        self.assertEqual(self.client.post(url).status_code, 200)
        plan.refresh_from_db()
        self.assertEqual(
            plan.checked_ingredients,
            sorted(plan.product.parents.values_list("pk", flat=True)),
        )
        self.client.post(url)
        plan.refresh_from_db()
        self.assertEqual(plan.checked_ingredients, [])

    def test_current_steps_follow_the_stages(self):
        def current():
            return [
                step["plan"].product.name
                for step in self.cards()[self.bread]["steps"]
                if step["is_current"]
            ]

        self.assertEqual(current(), [])
        self.start()
        self.assertEqual(current(), ["Starter"])
        starter = self.sub_plan("Starter")
        toggle_all_url = reverse(
            "workshop:production-plan-ingredients-toggle-all",
            kwargs={"pk": starter.pk},
        )
        sourdough = self.sub_plan("Sourdough")
        # The response moves the highlight to the next stage, and back on undo.
        response = self.client.post(toggle_all_url)
        self.assertEqual(current(), ["Sourdough"])
        self.assertContains(
            response, f'id="step-{sourdough.pk}" class="production-step is-current"'
        )
        response = self.client.post(toggle_all_url)
        self.assertEqual(current(), ["Starter"])
        self.assertContains(
            response, f'id="step-{starter.pk}" class="production-step is-current"'
        )
        self.assertContains(
            response, f'id="step-{sourdough.pk}" class="production-step"'
        )

    def choose(self, plan):
        self.client.cookies["production_steps"] = quote(
            json.dumps({self.root().pk: plan.pk})
        )

    def toggle_all(self, plan):
        return self.client.post(
            reverse(
                "workshop:production-plan-ingredients-toggle-all",
                kwargs={"pk": plan.pk},
            )
        )

    def current(self):
        return [
            step["plan"].product.name
            for step in self.cards()[self.bread]["steps"]
            if step["is_current"]
        ]

    def test_chosen_dough_is_current_until_done(self):
        self.start()
        sourdough = self.sub_plan("Sourdough")
        self.choose(sourdough)
        self.assertEqual(self.current(), ["Sourdough"])
        self.assertEqual(
            [step["can_choose"] for step in self.cards()[self.bread]["steps"]],
            [True, False, True],
        )
        response = self.toggle_all(sourdough)
        self.assertContains(
            response,
            f'id="step-{self.root().pk}" class="production-step is-current"',
        )
        response = self.client.get(
            reverse("workshop:production-plan-steps", kwargs={"pk": self.root().pk})
        )
        self.assertContains(response, f'id="steps-{self.root().pk}"')

    def test_after_the_last_chosen_dough_the_first_open_one_is_current(self):
        self.start()
        self.choose(self.root())
        self.assertEqual(self.current(), ["Bread"])
        self.toggle_all(self.root())
        self.assertEqual(self.current(), ["Starter"])
        self.toggle_all(self.sub_plan("Starter"))
        self.toggle_all(self.sub_plan("Sourdough"))
        self.assertEqual(self.current(), [])

    def add_poolish(self):
        # A second pre dough, made at the same time as the sourdough.
        poolish = ProductFactory(
            name="Poolish", category=self.categories["pre-dough"], weight=200
        )
        add(poolish, self.products["wheat"], 100)
        add(poolish, self.products["water"], 100)
        add(self.bread, poolish, 200)
        self.client.get(self.url("production-plan-update", self.root().pk))
        self.start()

    def test_one_dough_of_a_stage_is_current(self):
        self.add_poolish()
        self.toggle_all(self.sub_plan("Starter"))
        self.assertEqual(self.current(), ["Sourdough"])
        self.toggle_all(self.sub_plan("Sourdough"))
        self.assertEqual(self.current(), ["Poolish"])

    def test_after_the_chosen_dough_the_highlight_doesnt_go_back(self):
        self.add_poolish()
        poolish = self.sub_plan("Poolish")
        self.choose(poolish)
        self.toggle_all(poolish)
        self.assertEqual(self.current(), ["Sourdough"])

    def test_broken_step_cookie_is_ignored(self):
        self.start()
        self.client.cookies["production_steps"] = "not json"
        self.assertEqual(self.current(), ["Starter"])

    def test_toggle_rejects_rows_of_other_plans(self):
        self.start()
        plan = self.sub_plan("Sourdough")
        other_row = self.sub_plan("Starter").product.parents.first()
        self.assertEqual(self.toggle(plan, other_row).status_code, 400)

    def test_finished_plan_keeps_checks_read_only(self):
        self.start()
        plan = self.sub_plan("Sourdough")
        row = plan.product.parents.first()
        self.toggle(plan, row)
        self.root().set_state(ProductionPlan.State.PRODUCED)
        self.assertEqual(self.toggle(plan, row).status_code, 400)
        step = self.cards()[self.bread]["steps"][1]
        self.assertTrue(step["show_checks"])
        self.assertFalse(step["can_check"])
        self.assertTrue(step["rows"][0]["checked"])

    def test_htmx_action_returns_page_with_card(self):
        day_product = self.day_products[self.bread.pk]
        url = self.url("production-plan-cancel", self.root().pk)
        response = self.client.post(
            f"{url}?next={self.day_url()}", HTTP_HX_REQUEST="true", follow=True
        )
        self.assertContains(response, f'id="card-{day_product.pk}"')
        self.assertContains(response, 'id="production-summary"')
        self.assertTrue(self.root().is_canceled)


class NotesViewTest(ProductionPlanDayViewTest):
    def notes_url(self, day_product):
        return reverse(
            "workshop:notes",
            kwargs={"model": "shop.productiondayproduct", "object_id": day_product.pk},
        )

    def add_note(self, content="Dough was too warm"):
        day_product = self.day_products[self.bread.pk]
        return self.client.post(self.notes_url(day_product), {"content": content})

    def test_add_note(self):
        response = self.add_note()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dough was too warm")
        note = Note.objects.get()
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.content_object, self.day_products[self.bread.pk])
        self.assertContains(self.client.get(self.day_url()), "Dough was too warm")

    def test_empty_note_is_rejected(self):
        self.assertEqual(self.add_note("").status_code, 422)
        self.assertFalse(Note.objects.exists())

    def test_only_listed_models(self):
        response = self.client.get(
            reverse("workshop:notes", kwargs={"model": "users.user", "object_id": 1})
        )
        self.assertEqual(response.status_code, 404)

    def test_update_and_delete_own_note(self):
        self.add_note()
        note = Note.objects.get()
        self.client.post(
            reverse("workshop:note-update", kwargs={"pk": note.pk}),
            {"content": "Baked 5 minutes longer"},
        )
        note.refresh_from_db()
        self.assertEqual(note.content, "Baked 5 minutes longer")
        self.client.post(reverse("workshop:note-delete", kwargs={"pk": note.pk}))
        self.assertFalse(Note.objects.exists())

    def test_other_users_cannot_change_note(self):
        self.add_note()
        note = Note.objects.get()
        other = User.objects.create_user(
            username="other", email="other@example.com", password="x", is_staff=True
        )
        self.client.force_login(other)
        response = self.client.post(
            reverse("workshop:note-delete", kwargs={"pk": note.pk})
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Note.objects.exists())

    def test_note_survives_plan_update(self):
        self.add_note()
        old_root = self.root()
        self.client.get(self.url("production-plan-update", old_root.pk))
        self.assertNotEqual(self.root().pk, old_root.pk)
        self.assertContains(self.client.get(self.day_url()), "Dough was too warm")


class ProductionPlanDayQueryTest(ProductionPlanDayViewTest):
    def count_queries(self):
        with CaptureQueriesContext(connection) as queries:
            self.cards()
        return len(queries)

    def test_queries_dont_grow_with_products(self):
        self.start()
        self.client.post(
            reverse(
                "workshop:notes",
                kwargs={
                    "model": "shop.productiondayproduct",
                    "object_id": self.day_products[self.bread.pk].pk,
                },
            ),
            {"content": "Note"},
        )
        self.cards()
        before = self.count_queries()
        for name in ["Rye bread", "Wheat bread"]:
            bread = ProductFactory(
                name=name, category=self.categories["bread"], is_sellable=True
            )
            add(bread, self.products["sourdough"], 300)
            add(bread, self.products["wheat"], 500)
            ProductionDayProduct.objects.create(
                production_day=self.production_day, product=bread, max_quantity=5
            )
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
        self.assertEqual(self.count_queries(), before)


class ProductionDayDetailViewTest(ProductionPlanDayViewTest):
    def setUp(self):
        super().setUp()
        day = self.production_day.day_of_sale
        self.prev_day = ProductionDay.objects.create(day_of_sale=day - timedelta(1))
        self.next_day = ProductionDay.objects.create(day_of_sale=day + timedelta(1))

    def detail_url(self, production_day=None):
        return self.url(
            "production-day-detail", (production_day or self.production_day).pk
        )

    def detail(self):
        response = self.client.get(self.detail_url())
        self.assertEqual(response.status_code, 200)
        return response

    def start_day(self):
        for plan in ProductionPlan.objects.filter(
            production_day=self.production_day, parent_plan=None
        ):
            plan.set_production()

    def add_order(self):
        self.pos = PointOfSale.objects.create(name="Market")
        order = CustomerOrder.objects.create(
            production_day=self.production_day, point_of_sale=self.pos, address=""
        )
        CustomerOrderPosition.objects.create(
            order=order, product=self.bread, quantity=3, production_plan=self.root()
        )
        return order

    def assert_links(self, response, urls):
        for url in urls:
            self.assertContains(response, f'"{url}', msg_prefix=url)

    def day_urls(self, *names):
        pk = self.production_day.pk
        return [reverse(f"workshop:{name}", kwargs={"pk": pk}) for name in names]

    def test_every_control_of_a_planned_day(self):
        pk = self.production_day.pk
        response = self.detail()
        self.assert_links(
            response,
            [
                self.detail_url(self.prev_day),
                self.detail_url(self.next_day),
                reverse("workshop:production-day-calendar"),
                reverse("workshop:production-day-add"),
                reverse("workshop:production-day-delete", kwargs={"pk": pk}),
                reverse("workshop:production-day-copy", kwargs={"pk": pk}),
                reverse("workshop:order-list") + f"?production_day={pk}",
                reverse("workshop:production-day-export", kwargs={"pk": pk}),
                reverse("workshop:order-add", kwargs={"production_day": pk}),
                reverse(
                    "workshop:production-day-reminder", kwargs={"production_day": pk}
                ),
                reverse(
                    "workshop:production-plans-start", kwargs={"production_day": pk}
                ),
                f"{self.day_url()}#card-{self.day_products[self.bread.pk].pk}",
                *self.day_urls(
                    "production-day-update",
                    "production-plan-production-day",
                    "production-day-meta-product",
                    "production-day-order-max-quantities",
                    "order-batch",
                ),
            ],
        )
        self.assertContains(response, 'id="orders"')
        self.assertContains(response, "data-print")
        self.assertNotContains(
            response,
            reverse("workshop:production-plans-finish", kwargs={"production_day": pk}),
        )

    def test_every_control_of_a_day_in_production(self):
        pk = self.production_day.pk
        order = self.add_order()
        self.start_day()
        response = self.detail()
        self.assert_links(
            response,
            [
                reverse(
                    "workshop:production-plans-finish", kwargs={"production_day": pk}
                ),
                reverse(
                    "workshop:pos-all-picked-up",
                    kwargs={"production_day": pk, "pos": self.pos.pk},
                ),
                reverse("workshop:order-is-picked-up", kwargs={"pk": order.pk}),
            ],
        )
        self.assertNotContains(
            response,
            reverse("workshop:production-plans-start", kwargs={"production_day": pk}),
        )
        self.assertNotContains(
            response,
            reverse("workshop:production-day-order-max-quantities", kwargs={"pk": pk}),
        )
        self.assertEqual(response.context["stats"]["orders"], 1)
        self.assertEqual(response.context["stats"]["pieces"], 3)

    def test_one_filled_button_and_plan_in_menu(self):
        pk = self.production_day.pk
        start = reverse(
            "workshop:production-plans-start", kwargs={"production_day": pk}
        )
        finish = reverse(
            "workshop:production-plans-finish", kwargs={"production_day": pk}
        )

        def primary_and_menu():
            actions = self.detail().context["day_actions"]
            return (
                [a.url.split("?")[0] for a in actions.buttons if a.kind == "primary"],
                [a.url.split("?")[0] for a in actions.menu],
            )

        primary, menu = primary_and_menu()
        self.assertEqual(primary, [start])
        self.assertIn(self.day_url(), menu)
        self.start_day()
        primary, menu = primary_and_menu()
        self.assertEqual(primary, [finish])
        self.assertNotIn(finish, menu)

    def test_delivery_bill_shows_the_short_point_of_sale_name(self):
        self.add_order()
        self.pos.short_name = "MKT"
        self.pos.save()
        response = self.detail()
        self.assertContains(response, '<h3 class="delivery-bill-title">MKT ')

    def test_delivery_bill_only_marks_canceled_products(self):
        self.add_order()
        bill = self.detail().content.decode().split('id="orders"')[1]
        self.assertNotIn("geplant", bill)
        plan = self.root()
        plan.state = ProductionPlan.State.CANCELED
        plan.save()
        bill = self.detail().content.decode().split('id="orders"')[1]
        self.assertIn("abgebrochen", bill)

    def test_note_column_only_with_notes(self):
        order = self.add_order()
        self.assertNotContains(self.detail(), 'class="col-note"')
        Note.objects.create(content_object=order, user=self.user, content="Geschnitten")
        response = self.detail()
        self.assertContains(response, 'class="col-note"')
        self.assertContains(response, "Geschnitten")

    def test_delete_is_disabled_with_orders(self):
        self.add_order()
        response = self.detail()
        delete = [a for a in response.context["day_actions"] if a.danger][0]
        self.assertTrue(delete.disabled)
        self.assertNotContains(response, f'href="{delete.url}"')

    def test_product_row_links_to_recipe_and_plan(self):
        response = self.detail()
        self.assertContains(
            response, f'href="{self.url("product-detail", self.bread.pk)}"'
        )
        card = f"card-{self.day_products[self.bread.pk].pk}"
        self.assertContains(response, f'href="{self.day_url()}#{card}"')
        self.assertContains(self.client.get(self.day_url()), f'id="{card}"')
        self.assertNotContains(response, "stretched-link day-product-name")

    def test_plan_card_url_matches_the_card(self):
        card = f"card-{self.day_products[self.bread.pk].pk}"
        self.assertEqual(self.root().get_card_url(), f"{self.day_url()}#{card}")

    def test_product_rows(self):
        self.add_order()
        rows = {
            row["day_product"].product: row
            for row in self.detail().context["product_rows"]
        }
        self.assertEqual(rows[self.bread]["ordered"], 3)
        self.assertEqual(rows[self.bread]["percent"], 30)
        self.assertFalse(rows[self.bread]["is_over"])

    def test_product_mapping_only_when_present(self):
        self.assertNotContains(self.detail(), "day-mappings")
        ProductMapping.objects.create(
            source_product=self.cake,
            target_product=self.bread,
            production_day=self.production_day,
            matched_count=2,
        )
        self.assertContains(self.detail(), "day-mappings")

    def test_day_forms_return_to_the_day(self):
        pk = self.production_day.pk
        for name in ["order-batch", "production-day-meta-product"]:
            response = self.client.get(reverse(f"workshop:{name}", kwargs={"pk": pk}))
            self.assertContains(
                response, f'href="{self.detail_url()}"', msg_prefix=name
            )

    def test_pos_all_picked_up_returns_to_the_day(self):
        order = self.add_order()
        response = self.client.post(
            reverse(
                "workshop:pos-all-picked-up",
                kwargs={"production_day": self.production_day.pk, "pos": self.pos.pk},
            )
        )
        self.assertRedirects(
            response, f"{self.detail_url()}#orders", fetch_redirect_response=False
        )
        self.assertTrue(order.positions.get().is_picked_up)

    def test_pick_up_toggle_swaps_only_its_delivery_bill(self):
        order = self.add_order()
        url = reverse(
            "workshop:pos-all-picked-up",
            kwargs={"production_day": self.production_day.pk, "pos": self.pos.pk},
        )
        response = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertTrue(order.positions.get().is_picked_up)
        self.assertTemplateUsed(response, "workshop/includes/delivery_bill.html")
        self.assertTemplateNotUsed(response, "workshop/base.html")
        self.assertContains(response, f'id="delivery-bill-{self.pos.pk}"')
        self.assertContains(response, "checked")
        self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertFalse(order.positions.get().is_picked_up)


class ProductionDayCalendarViewTest(ProductionDayDetailViewTest):
    def calendar(self, **params):
        response = self.client.get(reverse("workshop:production-day-calendar"), params)
        self.assertEqual(response.status_code, 200)
        return response

    def cells(self, response):
        return {
            cell["date"]: cell
            for week in response.context["calendar"]["weeks"]
            for cell in week
        }

    def test_month_shows_production_days(self):
        self.add_order()
        self.start()
        day = self.production_day.day_of_sale
        response = self.calendar(month=day.strftime("%Y-%m"))
        cell = self.cells(response)[day]
        self.assertEqual(cell["day"], self.production_day)
        self.assertEqual(cell["day"].orders, 1)
        self.assertEqual(cell["state_css_class"], "bg-warning")
        self.assertContains(response, f'href="{self.detail_url()}"')
        self.assertTemplateUsed(response, "workshop/productionday_calendar.html")

    def test_month_lists_the_products_of_a_day(self):
        self.add_order()
        day = self.production_day.day_of_sale
        response = self.calendar(month=day.strftime("%Y-%m"))
        products = {p["name"]: p for p in self.cells(response)[day]["products"]}
        self.assertEqual(products["Bread"]["ordered"], 3)
        self.assertEqual(products["Bread"]["max"], 10)
        self.assertEqual(products["Cake"]["ordered"], 0)
        self.assertContains(response, 'class="day-calendar-tip"')

    def test_free_future_day_can_be_added(self):
        free = self.next_day.day_of_sale + timedelta(days=1)
        response = self.calendar(month=free.strftime("%Y-%m"))
        self.assertTrue(self.cells(response)[free]["can_add"])
        self.assertContains(
            response,
            f"{reverse('workshop:production-day-add')}?day_of_sale={free.isoformat()}",
        )

    def test_add_view_takes_the_date(self):
        response = self.client.get(
            reverse("workshop:production-day-add"), {"day_of_sale": "2030-05-17"}
        )
        self.assertEqual(
            str(response.context["form"].initial["day_of_sale"]), "2030-05-17"
        )

    def test_compact_calendar_links_to_the_plan(self):
        day = self.production_day.day_of_sale
        response = self.calendar(
            month=day.strftime("%Y-%m"),
            compact=1,
            link="plan",
            selected=day.isoformat(),
        )
        self.assertTemplateNotUsed(response, "workshop/base.html")
        cell = self.cells(response)[day]
        self.assertTrue(cell["is_selected"])
        self.assertEqual(cell["url"], self.day_url())
        self.assertContains(response, 'hx-target="#production-day"')

    def test_week_shows_its_seven_days_with_products(self):
        self.add_order()
        day = self.production_day.day_of_sale
        monday = day - timedelta(days=day.weekday())
        # Any date of the week opens it.
        response = self.calendar(week=day.isoformat())
        calendar = response.context["calendar"]
        self.assertTrue(calendar["is_week"])
        self.assertEqual(
            [cell["date"] for week in calendar["weeks"] for cell in week],
            [monday + timedelta(days=offset) for offset in range(7)],
        )
        cell = self.cells(response)[day]
        self.assertEqual(cell["day"], self.production_day)
        products = {product["name"]: product for product in cell["products"]}
        self.assertEqual(products["Bread"]["ordered"], 3)
        self.assertEqual(products["Bread"]["max"], 10)
        self.assertContains(response, 'class="day-calendar-products"')
        self.assertNotContains(response, 'class="day-calendar-tip"')
        self.assertContains(response, f'href="{self.detail_url()}"')

    def test_week_links_to_its_neighbours_and_its_month(self):
        url = reverse("workshop:production-day-calendar")
        # Thursday 1 January 2026: the week starts in December.
        calendar = self.calendar(week="2026-01-01").context["calendar"]
        self.assertEqual(calendar["week_number"], 1)
        self.assertEqual(calendar["previous_url"], f"{url}?week=2025-12-22")
        self.assertEqual(calendar["next_url"], f"{url}?week=2026-01-05")
        self.assertEqual(calendar["month_view_url"], f"{url}?month=2026-01")

    def test_month_links_to_its_first_week(self):
        url = reverse("workshop:production-day-calendar")
        calendar = self.calendar(month="2030-05").context["calendar"]
        self.assertFalse(calendar["is_week"])
        self.assertEqual(calendar["week_view_url"], f"{url}?week=2030-04-29")

    def test_day_picker_stays_a_month(self):
        response = self.calendar(week="2030-05-17", compact=1)
        self.assertFalse(response.context["calendar"]["is_week"])

    def test_broken_week_falls_back_to_the_month(self):
        response = self.calendar(week="nope")
        self.assertFalse(response.context["calendar"]["is_week"])

    def test_broken_month_falls_back_to_today(self):
        response = self.calendar(month="nope", link="nope")
        self.assertEqual(
            response.context["calendar"]["month"], timezone.now().date().replace(day=1)
        )

    def test_day_picker_on_both_pages(self):
        self.assertContains(self.detail(), "day-picker-toggle")
        self.assertContains(self.client.get(self.day_url()), "day-picker-toggle")

    def test_sidebar(self):
        self.assertContains(
            self.calendar(),
            f'aria-current="page" href="{reverse("workshop:production-day-calendar")}"',
            count=1,
        )
        self.assertContains(
            self.detail(),
            f'aria-current="page" href="{reverse("workshop:production-day-next")}"',
            count=1,
        )


class PickupEmailsViewTest(ProductionDayDetailViewTest):
    def reminder_url(self, production_day=None):
        return reverse(
            "workshop:production-day-reminder",
            kwargs={"production_day": (production_day or self.production_day).pk},
        )

    def test_sidebar_opens_the_next_production_day(self):
        response = self.client.get(reverse("workshop:production-day-reminder-next"))
        upcoming = ProductionDay.objects.upcoming().first()
        self.assertRedirects(response, self.reminder_url(upcoming))

    def test_switcher_loads_the_pages(self):
        response = self.client.get(self.reminder_url())
        self.assertEqual(response.status_code, 200)
        switch = response.context["day_switch"]
        self.assertEqual(switch["previous_url"], self.reminder_url(self.prev_day))
        self.assertEqual(switch["next_url"], self.reminder_url(self.next_day))
        self.assertContains(response, f'href="{switch["next_url"]}"')
        self.assertNotContains(response, f'hx-get="{switch["next_url"]}"')
        self.assertFalse(switch["calendar"]["can_add_day"])
        self.assertNotContains(response, reverse("workshop:production-day-add"))
        self.assertContains(
            response,
            f'aria-current="page" href="{reverse("workshop:production-day-reminder-next")}"',
            count=1,
        )


class PickupEmailsEditorTest(PickupEmailsViewTest):
    def post(self, button, url=None, **data):
        return self.client.post(
            url or self.reminder_url(),
            {
                "subject": "Abholung",
                "body": json.dumps(
                    {
                        "blocks": [
                            {
                                "key": "a",
                                "type": "unstyled",
                                "text": "Hallo {{ first_name }}",
                                "depth": 0,
                                "inlineStyleRanges": [],
                                "entityRanges": [],
                            }
                        ],
                        "entityMap": {},
                    }
                ),
                "point_of_sale": "",
                "production_day": self.production_day.pk,
                button: "",
                **data,
            },
        )

    def draft_url(self, draft):
        return reverse(
            "workshop:production-day-reminder",
            kwargs={"production_day": self.production_day.pk, "pk": draft.pk},
        )

    def test_save_keeps_a_draft(self):
        response = self.post("save")
        draft = ReminderMessage.objects.get()
        self.assertTrue(draft.is_planned)
        self.assertRedirects(response, self.draft_url(draft))
        page = self.client.get(self.draft_url(draft))
        self.assertEqual(list(page.context["drafts"]), [draft])
        self.assertContains(page, 'class="reminder-item reminder-draft is-active"')

    def test_send_queues_and_starts_a_new_email(self):
        response = self.post("send")
        self.assertRedirects(response, self.reminder_url())
        self.assertTrue(ReminderMessage.objects.get().is_planned_sending)

    def test_preview_fills_in_example_data(self):
        response = self.post(
            "preview",
            url=reverse(
                "workshop:production-day-reminder-preview",
                kwargs={"production_day": self.production_day.pk},
            ),
            subject="Für {{ first_name }}",
        )
        self.assertContains(response, "Für Manu")
        self.assertContains(response, "Hallo Manu")
        self.assertTemplateNotUsed(response, "workshop/base.html")

    def test_lists_fill_in_the_shop_name(self):
        self.post("save", subject="[{{ site_name }}] Abholung")
        page = self.client.get(self.reminder_url())
        draft = page.context["drafts"][0]
        self.assertEqual(draft.display_subject, f"[{self.tenant.name}] Abholung")

    def test_send_needs_recipients(self):
        def send():
            actions = self.client.get(self.reminder_url()).context["editor_actions"]
            return [a for a in actions if a.submit_name == "send"][0]

        self.assertTrue(send().disabled)
        self.add_order()
        self.assertFalse(send().disabled)
        self.assertEqual(send().badge, 1)

    def test_recipients_by_point_of_sale(self):
        self.add_order()
        response = self.client.get(self.reminder_url())
        self.assertEqual(
            response.context["recipient_counts"], {"": 1, str(self.pos.pk): 1}
        )
        self.assertEqual(response.context["recipient_count"], 1)

    def test_delete_draft(self):
        self.post("save")
        draft = ReminderMessage.objects.get()
        self.client.post(
            reverse(
                "workshop:production-day-reminder-delete",
                kwargs={"production_day": self.production_day.pk, "pk": draft.pk},
            )
        )
        self.assertFalse(ReminderMessage.objects.exists())


class CustomerExportTest(NumberCircleTestCase):
    def test_ready2order_uses_customer_number(self):
        self.set_start(customer_number_start=20000)
        client = TenantClient(self.tenant)
        client.force_login(self.user)
        response = client.get(reverse("workshop:customer-export-ready-2-order"))
        self.assertEqual(response.status_code, 200)
        rows = response.content.decode("iso-8859-1").splitlines()
        self.assertEqual(rows[0].split(",")[0], "kundennummer")
        self.assertEqual(
            [row.split(",")[0] for row in rows[1:]],
            [str(20000 + self.customer.pk)],
        )

    def test_easybill_export_matches_import_template(self):
        self.user.first_name = "Matthias"
        self.user.last_name = "Brück"
        self.user.save()
        client = TenantClient(self.tenant)
        client.force_login(self.user)
        response = client.get(reverse("workshop:customer-export-easybill"))
        self.assertEqual(response.status_code, 200)
        rows = response.content.decode("iso-8859-1").splitlines()
        self.assertEqual(
            rows[0],
            "Kundennummer,Name,Vorname,Straße/Hausnummer,Postleitzahl,Ort,"
            "Telefon 1,E-Mail",
        )
        self.assertEqual(
            rows[1].split(",")[:3],
            [str(self.customer.customer_number), "Brück", "Matthias"],
        )


class CleverUnitTest(SimpleTestCase):
    def test_clever_unit(self):
        with translation.override("de"):
            self.assertEqual(clever_unit(80760), "80,76\xa0kg")
            self.assertEqual(clever_unit(12345.6), "12,346\xa0kg")
            self.assertEqual(clever_unit(10000), "10\xa0kg")
            self.assertEqual(clever_unit(9999.4), "9999\xa0g")
            self.assertEqual(clever_unit(1250), "1250\xa0g")
            self.assertEqual(clever_unit(72.94), "72,9\xa0g")
            self.assertEqual(clever_unit(15000, "ml"), "15\xa0l")
            self.assertEqual(clever_unit(3, "Stk"), "3\xa0Stk")
            self.assertEqual(clever_unit(None), "")


class CustomerOrderExportTest(NumberCircleTestCase):
    def test_easybill_export_uses_vat_rate_of_position(self):
        order = CustomerOrder.objects.create(
            production_day=ProductionDay.objects.create(
                day_of_sale=timezone.now().date()
            ),
            customer=self.customer,
            address="",
        )
        for product in [ProductFactory(), ProductFactory(vat_rate=VatRate.STANDARD)]:
            CustomerOrderPosition.objects.create(
                order=order, product=product, quantity=1
            )
        client = TenantClient(self.tenant)
        client.force_login(self.user)
        response = client.get(reverse("workshop:order-export-easybill"))
        self.assertEqual(response.status_code, 200)
        rows = [
            row.split(";") for row in response.content.decode("iso-8859-1").splitlines()
        ]
        column = rows[0].index("vat_percent")
        self.assertEqual(sorted(row[column] for row in rows[1:]), ["19.0000", "7.0000"])


# https://github.com/bruecksen/bakeup/issues/548
def test_swapping_product_in_production_day_form_deletes_its_planned_plan(
    client, staff_user, planned_production_day, sellable_products
):
    client.force_login(staff_user)
    bread_row, broetchen_row = ProductionDayProduct.objects.filter(
        production_day=planned_production_day
    ).order_by("product__name")

    # The row that sold Bread now sells Baguette, the other row stays.
    response = client.post(
        reverse(
            "workshop:production-day-update", kwargs={"pk": planned_production_day.pk}
        ),
        {
            "day_of_sale": planned_production_day.day_of_sale.isoformat(),
            "form-TOTAL_FORMS": 2,
            "form-INITIAL_FORMS": 2,
            "form-0-id": bread_row.pk,
            "form-0-product": sellable_products["Baguette"].pk,
            "form-0-max_quantity": 10,
            "form-1-id": broetchen_row.pk,
            "form-1-product": sellable_products["Brötchen"].pk,
            "form-1-max_quantity": 10,
        },
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "workshop:production-day-detail", kwargs={"pk": planned_production_day.pk}
    )
    assert list(
        ProductionDayProduct.objects.filter(production_day=planned_production_day)
        .order_by("product__name")
        .values_list("product__name", flat=True)
    ) == ["Baguette", "Brötchen"]
    assert list(
        ProductionPlan.objects.filter(
            production_day=planned_production_day, parent_plan=None
        )
        .order_by("product__product_template__name")
        .values_list("product__product_template__name", "state")
    ) == [
        ("Baguette", ProductionPlan.State.PLANNED),
        ("Brötchen", ProductionPlan.State.PLANNED),
    ]
