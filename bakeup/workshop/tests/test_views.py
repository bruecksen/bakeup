import json
from datetime import timedelta
from io import StringIO
from urllib.parse import quote

import pytest
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.db import connection
from django.db.models import Sum
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation
from django_tenants.test.client import TenantClient

from bakeup.contrib.models import Note
from bakeup.core.models import UOM
from bakeup.pages.tests.factories import DocumentFactory, EmailSettingsFactory
from bakeup.shop.models import (
    Customer,
    CustomerOrder,
    CustomerOrderPosition,
    CustomerOrderTemplateSkip,
    PointOfSale,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.shop.tests.factories import (
    CustomerOrderFactory,
    CustomerOrderPositionFactory,
    CustomerOrderTemplateFactory,
    CustomerOrderTemplatePositionFactory,
    CustomerOrderTemplateSkipFactory,
)
from bakeup.users.models import User
from bakeup.users.tests.factories import UserFactory
from bakeup.workshop.models import (
    Instruction,
    Product,
    ProductHierarchy,
    ProductionPlan,
    VatRate,
)
from bakeup.workshop.templatetags.workshop_tags import clever_unit
from bakeup.workshop.tests.factories import (
    ProductFactory,
    ProductionDayFactory,
    ProductionDayProductFactory,
    add,
)
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


def abo_order_positions():
    return list(
        CustomerOrderPosition.objects.order_by(
            "order__customer", "product__name"
        ).values_list(
            "order__customer", "order__production_day", "product__name", "quantity"
        )
    )


def abo_skips():
    return list(
        CustomerOrderTemplateSkip.objects.order_by(
            "customer", "product__name"
        ).values_list("customer", "production_day", "product__name")
    )


@pytest.fixture
def abo_customer(abo_products):
    # A customer with a running abo of two Bread and three Brötchen.
    customer = UserFactory().customer
    abo = CustomerOrderTemplateFactory(customer=customer)
    for name, quantity in [("Bread", 2), ("Brötchen", 3)]:
        CustomerOrderTemplatePositionFactory(
            order_template=abo, product=abo_products[name], quantity=quantity
        )
    return customer


@pytest.fixture
def abo_order(abo_customer, abo_products):
    # The abo customer's order of a day that sells Bread and Brötchen.
    production_day = ProductionDayFactory()
    order = CustomerOrderFactory(customer=abo_customer, production_day=production_day)
    for name, quantity in [("Bread", 2), ("Brötchen", 3)]:
        ProductionDayProductFactory(
            production_day=production_day,
            product=abo_products[name],
            is_published=True,
        )
        CustomerOrderPositionFactory(
            order=order, product=abo_products[name], quantity=quantity
        )
    return order


@pytest.mark.parametrize(
    "publish, positions, shown_messages",
    [
        # Only the description changes: nothing became orderable.
        (False, [], []),
        # The Bread gets published in the same save.
        (True, [("Bread", 2)], ["1 Abo-Bestellung für Bread angelegt."]),
    ],
)
def test_saving_a_production_day_creates_abo_orders_only_for_newly_published_products(
    client,
    staff_user,
    abo_customer,
    abo_products,
    production_day_form_data,
    publish,
    positions,
    shown_messages,
):
    # Regression test for #608: every save of a day created abo orders.
    production_day = ProductionDayFactory()
    bread_row = ProductionDayProductFactory(
        production_day=production_day, product=abo_products["Bread"], is_published=False
    )
    # Published already, so its abo order is not due with this save.
    broetchen_row = ProductionDayProductFactory(
        production_day=production_day,
        product=abo_products["Brötchen"],
        is_published=True,
    )
    client.force_login(staff_user)

    response = client.post(
        reverse("workshop:production-day-update", kwargs={"pk": production_day.pk}),
        production_day_form_data(
            production_day.day_of_sale,
            [
                {
                    "id": bread_row.pk,
                    "product": abo_products["Bread"],
                    "is_published": publish,
                },
                {
                    "id": broetchen_row.pk,
                    "product": abo_products["Brötchen"],
                    "is_published": True,
                },
            ],
            description="Mit Sauerteig",
        ),
    )

    assert response.status_code == 302, response.content.decode()[:500]
    production_day.refresh_from_db()
    assert production_day.description == "Mit Sauerteig"
    assert abo_order_positions() == [
        (abo_customer.pk, production_day.pk, name, quantity)
        for name, quantity in positions
    ]
    assert [
        str(message) for message in get_messages(response.wsgi_request)
    ] == shown_messages


def test_moving_a_production_day_keeps_the_opt_out_when_the_product_gets_published(
    client, staff_user, abo_customer, abo_products, production_day_form_data
):
    production_day = ProductionDayFactory()
    rows = {
        name: ProductionDayProductFactory(
            production_day=production_day,
            product=abo_products[name],
            is_published=False,
        )
        for name in ["Bread", "Brötchen"]
    }
    CustomerOrderTemplateSkipFactory(
        customer=abo_customer,
        production_day=production_day,
        product=abo_products["Bread"],
    )
    day_of_sale = production_day.day_of_sale + timedelta(days=14)
    client.force_login(staff_user)

    response = client.post(
        reverse("workshop:production-day-update", kwargs={"pk": production_day.pk}),
        production_day_form_data(
            day_of_sale,
            [
                {"id": row.pk, "product": abo_products[name], "is_published": True}
                for name, row in rows.items()
            ],
        ),
    )

    assert response.status_code == 302, response.content.decode()[:500]
    production_day.refresh_from_db()
    assert production_day.day_of_sale == day_of_sale
    # The Brötchen, but not the Bread the customer opted out of.
    assert abo_order_positions() == [
        (abo_customer.pk, production_day.pk, "Brötchen", 3)
    ]


def test_staff_deleting_an_abo_order_records_the_opt_out(client, staff_user, abo_order):
    client.force_login(staff_user)

    response = client.post(
        reverse("workshop:order-delete", kwargs={"pk": abo_order.pk})
    )

    assert response.status_code == 302
    assert response.url == reverse("workshop:order-list")
    assert abo_order_positions() == []
    assert abo_skips() == [
        (abo_order.customer_id, abo_order.production_day_id, "Bread"),
        (abo_order.customer_id, abo_order.production_day_id, "Brötchen"),
    ]


def test_staff_deleting_an_order_in_production_keeps_it_and_records_no_opt_out(
    client, staff_user, abo_order
):
    production_day = abo_order.production_day
    # Plans from the orders, which links the positions to them.
    production_day.create_or_update_production_plans(
        state=ProductionPlan.State.IN_PRODUCTION
    )
    client.force_login(staff_user)

    response = client.post(
        reverse("workshop:order-delete", kwargs={"pk": abo_order.pk})
    )

    assert response.status_code == 302
    assert abo_order_positions() == [
        (abo_order.customer_id, production_day.pk, "Bread", 2),
        (abo_order.customer_id, production_day.pk, "Brötchen", 3),
    ]
    assert abo_skips() == []


@pytest.mark.parametrize(
    "broetchen_quantity, positions, skipped",
    [
        # Nothing left: the whole order is deleted.
        (0, [], ["Bread", "Brötchen"]),
        # Only the Bread is removed from the order.
        (3, [("Brötchen", 3)], ["Bread"]),
    ],
)
def test_staff_removing_abo_products_in_the_batch_orders_records_the_opt_out(
    client, staff_user, abo_order, abo_products, broetchen_quantity, positions, skipped
):
    customer, production_day = abo_order.customer, abo_order.production_day
    client.force_login(staff_user)

    response = client.post(
        reverse("workshop:order-batch", kwargs={"pk": production_day.pk}),
        {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 1,
            "form-0-customer": customer.pk,
            f"form-0-product_{abo_products['Bread'].pk}": 0,
            f"form-0-product_{abo_products['Brötchen'].pk}": broetchen_quantity,
        },
    )

    assert response.status_code == 302, response.content.decode()[:500]
    assert abo_order_positions() == [
        (customer.pk, production_day.pk, name, quantity) for name, quantity in positions
    ]
    assert abo_skips() == [(customer.pk, production_day.pk, name) for name in skipped]


def test_staff_removing_a_position_in_the_order_form_records_the_opt_out(
    client, staff_user, abo_order, abo_products
):
    bread_position, broetchen_position = abo_order.positions.order_by("product__name")
    client.force_login(staff_user)

    response = client.post(
        reverse("workshop:order-update", kwargs={"pk": abo_order.pk}),
        {
            "form-TOTAL_FORMS": 2,
            "form-INITIAL_FORMS": 2,
            "form-0-id": bread_position.pk,
            "form-0-product": abo_products["Bread"].pk,
            "form-0-quantity": 2,
            "form-0-DELETE": "on",
            "form-1-id": broetchen_position.pk,
            "form-1-product": abo_products["Brötchen"].pk,
            "form-1-quantity": 3,
        },
    )

    assert response.status_code == 302, response.content.decode()[:500]
    assert abo_order_positions() == [
        (abo_order.customer_id, abo_order.production_day_id, "Brötchen", 3)
    ]
    assert abo_skips() == [
        (abo_order.customer_id, abo_order.production_day_id, "Bread")
    ]


def test_removing_a_product_from_a_day_records_the_opt_out_of_customers_with_an_order(
    client, staff_user, abo_order, abo_products, production_day_form_data
):
    production_day = abo_order.production_day
    with_order = abo_order.customer
    # Subscribed to the Bread too, but without an order on this day.
    without_order = UserFactory().customer
    CustomerOrderTemplatePositionFactory(
        order_template__customer=without_order,
        product=abo_products["Bread"],
        quantity=1,
    )
    bread_row, broetchen_row = ProductionDayProduct.objects.filter(
        production_day=production_day
    ).order_by("product__name")
    client.force_login(staff_user)

    # Staff confirm that the Bread and its orders are removed from the day.
    response = client.post(
        reverse("workshop:production-day-product-delete", kwargs={"pk": bread_row.pk})
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "workshop:production-day-detail", kwargs={"pk": production_day.pk}
    )
    assert abo_order_positions() == [(with_order.pk, production_day.pk, "Brötchen", 3)]
    assert abo_skips() == [(with_order.pk, production_day.pk, "Bread")]

    # The Bread comes back, published.
    response = client.post(
        reverse("workshop:production-day-update", kwargs={"pk": production_day.pk}),
        production_day_form_data(
            production_day.day_of_sale,
            [
                {
                    "id": broetchen_row.pk,
                    "product": abo_products["Brötchen"],
                    "is_published": True,
                },
                {"product": abo_products["Bread"], "is_published": True},
            ],
        ),
    )

    assert response.status_code == 302, response.content.decode()[:500]
    # Only the customer who lost no order gets one.
    assert abo_order_positions() == sorted(
        [
            (with_order.pk, production_day.pk, "Brötchen", 3),
            (without_order.pk, production_day.pk, "Bread", 1),
        ]
    )


def test_staff_changing_an_abo_creates_the_orders_of_upcoming_published_days(
    client, staff_user, abo_products
):
    customer = UserFactory().customer
    production_day = ProductionDayFactory()
    ProductionDayProductFactory(
        production_day=production_day, product=abo_products["Bread"], is_published=True
    )
    client.force_login(staff_user)

    response = client.post(
        reverse("workshop:customer-abo"),
        {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 1,
            "form-0-customer": customer.pk,
            f"form-0-product_{abo_products['Bread'].pk}": 2,
        },
    )

    assert response.status_code == 302, response.content.decode()[:500]
    assert abo_order_positions() == [(customer.pk, production_day.pk, "Bread", 2)]


def test_staff_changing_abos_confirms_every_created_order_with_the_attachment(
    client, staff_user, abo_products, mailoutbox, django_capture_on_commit_callbacks
):
    EmailSettingsFactory(
        email_subject_prefix="",
        send_email_order_confirm=True,
        email_order_confirm_subject="Bestellt",
        email_order_confirm_attachment=DocumentFactory(
            title="AGB.pdf", file__data=b"%PDF-1.4 AGB"
        ),
    )
    bread = abo_products["Bread"]
    customers = [
        UserFactory(email=email).customer
        for email in ["anna@example.com", "bernd@example.com"]
    ]
    production_days = [ProductionDayFactory(), ProductionDayFactory()]
    for production_day in production_days:
        ProductionDayProductFactory(
            production_day=production_day, product=bread, is_published=True
        )
    client.force_login(staff_user)

    # The mails are sent when the transaction of the request commits.
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            reverse("workshop:customer-abo"),
            {
                "form-TOTAL_FORMS": 2,
                "form-INITIAL_FORMS": 2,
                "form-0-customer": customers[0].pk,
                f"form-0-product_{bread.pk}": 2,
                "form-1-customer": customers[1].pk,
                f"form-1-product_{bread.pk}": 3,
            },
        )

    assert response.status_code == 302, response.content.decode()[:500]
    assert sorted(abo_order_positions()) == [
        (customer.pk, production_day.pk, "Bread", quantity)
        for customer, quantity in zip(customers, [2, 3])
        for production_day in production_days
    ]
    # One mail per created order, and every mail of the request carries the
    # attachment.
    assert sorted((mail.to, mail.subject, mail.attachments) for mail in mailoutbox) == [
        (
            [f"{name}@example.com"],
            "Bestellt",
            [("AGB.pdf", b"%PDF-1.4 AGB", "application/pdf")],
        )
        for name in ["anna", "bernd"]
        for production_day in production_days
    ]


# Water temperature of the main dough of 10 breads (the bread_plan fixture),
# m * c of the ingredients besides the 2500 g water (4.19):
#   sourdough 2200 * 2.995 (half rye, half water) = 6589
#   wheat 4000 * 1.8 = 7200, flour 1000 * 1.8 = 1800, rye 2000 * 1.8 = 3600
#   salt 120 * 0.9 = 108
# That is 19297, with the water (10475) 29772. At 26 °C dough temperature
# and all ingredients at 20 °C:
#   (26 * 29772 - 20 * 19297) / 10475 = 388132 / 10475 = 37.05 °C


def water_temperature_url(plan):
    return reverse("workshop:production-plan-water-temperature", kwargs={"pk": plan.pk})


def production_day_url(production_day):
    return reverse(
        "workshop:production-plan-production-day", kwargs={"pk": production_day.pk}
    )


def water_temperature_data(plan, **temperatures):
    # The POST data of the calculator: every ingredient besides the water at
    # 20 °C, unless given by the name of the ingredient.
    data = {"dough": 26, "warming": 0}
    for row in plan.product.parents.select_related("child"):
        if row.child.name != "Water":
            data[f"row_{row.pk}"] = temperatures.pop(row.child.name, 20)
    return {**data, **temperatures}


def row_pks(plan):
    return {
        row.child.name: str(row.pk)
        for row in plan.product.parents.select_related("child")
    }


def test_production_day_offers_the_water_temperature_for_steps_with_water_only(
    client, staff_user, planned_production_day, bread_plan
):
    client.force_login(staff_user)
    broetchen_plan = ProductionPlan.objects.get(
        production_day=planned_production_day, product__name="Brötchen"
    )

    response = client.get(production_day_url(planned_production_day))

    assert response.status_code == 200
    steps = [step for card in response.context["cards"] for step in card["steps"]]
    # Brötchen are made of flour only.
    assert {step["plan"].product.name: bool(step["water"]) for step in steps} == {
        "Starter": True,
        "Sourdough": True,
        "Bread": True,
        "Brötchen": False,
    }
    content = response.content.decode()
    assert f'hx-get="{water_temperature_url(bread_plan)}"' in content
    assert water_temperature_url(broetchen_plan) not in content
    # Nothing is applied yet.
    assert "ingredient-temperature" not in content


def test_water_temperature_starts_with_the_defaults(client, staff_user, bread_plan):
    client.force_login(staff_user)

    response = client.get(water_temperature_url(bread_plan))

    assert response.status_code == 200
    water = response.context["water"]
    assert (water["dough"], water["warming"], water["applied"]) == (26, 0, False)
    assert [
        (row["name"], row["weight"], row["temperature"]) for row in water["rows"]
    ] == [
        ("Wheat flour", 4000, 20),
        ("Sourdough", 2200, 20),
        ("Rye flour", 2000, 20),
        ("Flour", 1000, 20),
        ("Salt", 120, 20),
    ]
    assert water["row"]["row"].child.name == "Water"
    assert water["result"] == pytest.approx(388132 / 10475)
    assert '<div class="water-temperature-value">37,1 °C</div>' in (
        response.content.decode()
    )


@pytest.mark.parametrize(
    "recipe_values, expected",
    [
        # The recipe says nothing, the settings do.
        ({}, (25, 1)),
        ({"dough_temperature": 24, "mixer_warming": 3}, (24, 3)),
        # Each value falls back on its own, no warming is a value too.
        ({"mixer_warming": 0}, (25, 0)),
    ],
)
def test_water_temperature_prefers_the_recipe_values_over_the_settings(
    client, staff_user, sellable_products, settings, recipe_values, expected
):
    settings.DOUGH_TEMPERATURE_DEFAULT = 25
    settings.MIXER_WARMING_DEFAULT = 1
    bread = sellable_products["Bread"]
    for field, value in recipe_values.items():
        setattr(bread, field, value)
    bread.save()
    # The plan gets a copy of the recipe.
    production_day = ProductionDayFactory()
    ProductionDayProductFactory(production_day=production_day, product=bread)
    production_day.create_or_update_production_plans(
        state=ProductionPlan.State.PLANNED, create_max_quantity=True
    )
    plan = ProductionPlan.objects.get(production_day=production_day, parent_plan=None)
    client.force_login(staff_user)

    response = client.get(water_temperature_url(plan))

    assert response.status_code == 200
    water = response.context["water"]
    assert (water["dough"], water["warming"]) == expected


def test_water_temperature_uses_the_ingredient_temperature_of_the_settings(
    client, staff_user, bread_plan, settings
):
    settings.INGREDIENT_TEMPERATURE_DEFAULT = 26
    client.force_login(staff_user)

    response = client.get(water_temperature_url(bread_plan))

    # Everything is as warm as the dough shall be, so is the water.
    assert response.context["water"]["result"] == pytest.approx(26)


def test_changing_a_temperature_previews_the_result_without_saving(
    client, staff_user, bread_plan
):
    client.force_login(staff_user)

    response = client.post(
        water_temperature_url(bread_plan),
        water_temperature_data(bread_plan, **{"Wheat flour": 10}),
    )

    assert response.status_code == 200
    # 4000 g wheat flour 10 °C colder: (388132 + 4000 * 1.8 * 10) / 10475
    assert response.context["water"]["result"] == pytest.approx(460132 / 10475)
    assert '<div class="water-temperature-value">43,9 °C</div>' in (
        response.content.decode()
    )
    assert "HX-Trigger" not in response.headers
    bread_plan.refresh_from_db()
    assert bread_plan.temperatures == {}


def test_a_water_temperature_that_is_not_reachable_shows_a_hint(
    client, staff_user, bread_plan
):
    client.force_login(staff_user)

    # (5 * 29772 - 385940) / 10475 is below 0 °C.
    response = client.post(
        water_temperature_url(bread_plan), water_temperature_data(bread_plan, dough=5)
    )

    assert response.status_code == 200
    water = response.context["water"]
    assert water["result"] == pytest.approx(-237080 / 10475)
    assert water["unreachable"] is True
    assert "water-temperature-hint" in response.content.decode()


def test_applying_stores_the_temperatures_and_shows_the_result_on_the_water_row(
    client, staff_user, planned_production_day, bread_plan
):
    client.force_login(staff_user)
    rows = row_pks(bread_plan)

    response = client.post(
        water_temperature_url(bread_plan),
        water_temperature_data(
            bread_plan, dough=24, warming=2, apply="1", **{"Wheat flour": 10}
        ),
    )

    assert response.status_code == 200
    # The event closes the modal, the steps of the card are swapped.
    assert response.headers["HX-Trigger"] == "closeProductionPlanModal"
    content = response.content.decode()
    assert f'id="steps-{bread_plan.pk}"' in content
    assert 'hx-swap-oob="outerMorph"' in content
    bread_plan.refresh_from_db()
    assert bread_plan.temperatures == {
        "dough": 24.0,
        "warming": 2.0,
        "rows": {
            rows["Sourdough"]: 20.0,
            rows["Wheat flour"]: 10.0,
            rows["Flour"]: 20.0,
            rows["Rye flour"]: 20.0,
            rows["Salt"]: 20.0,
        },
    }
    # ((24 - 2) * 29772 - (385940 - 72000)) / 10475 = 341044 / 10475 = 32.56
    badge = 'Water <span class="ingredient-temperature" title="Wassertemperatur">33 °C</span>'
    assert badge in content
    # Other devices see it on the page of the day, once.
    response = client.get(production_day_url(planned_production_day))
    assert response.content.decode().count(badge) == 1
    assert response.content.decode().count("ingredient-temperature") == 1


def test_applying_empty_fields_stores_the_defaults_of_dough_and_mixer(
    client, staff_user, bread_plan
):
    client.force_login(staff_user)
    data = dict.fromkeys(water_temperature_data(bread_plan), "")

    response = client.post(water_temperature_url(bread_plan), {**data, "apply": "1"})

    assert response.status_code == 200
    bread_plan.refresh_from_db()
    assert bread_plan.temperatures == {"dough": 26, "warming": 0, "rows": {}}


def test_an_invalid_temperature_is_rejected_and_not_stored(
    client, staff_user, bread_plan
):
    client.force_login(staff_user)

    response = client.post(
        water_temperature_url(bread_plan),
        water_temperature_data(bread_plan, dough="warm", apply="1"),
    )

    assert response.status_code == 422
    assert response.context["form"].errors == {"dough": ["Bitte eine Zahl eingeben."]}
    assert "HX-Trigger" not in response.headers
    bread_plan.refresh_from_db()
    assert bread_plan.temperatures == {}


def test_resetting_removes_the_water_temperature_again(
    client, staff_user, planned_production_day, bread_plan
):
    client.force_login(staff_user)
    bread_plan.set_temperatures({"dough": 24.0, "warming": 2.0, "rows": {}})

    response = client.post(water_temperature_url(bread_plan), {"reset": "1"})

    assert response.status_code == 200
    assert response.headers["HX-Trigger"] == "closeProductionPlanModal"
    assert "ingredient-temperature" not in response.content.decode()
    bread_plan.refresh_from_db()
    assert bread_plan.temperatures == {}
    response = client.get(production_day_url(planned_production_day))
    assert "ingredient-temperature" not in response.content.decode()


def test_a_finished_step_shows_the_water_temperature_but_no_menu(
    client, staff_user, planned_production_day, bread_plan
):
    client.force_login(staff_user)
    bread_plan.set_temperatures({"dough": 26, "warming": 0, "rows": {}})
    bread_plan.set_production()
    bread_plan.toggle_all_ingredients()

    response = client.get(production_day_url(planned_production_day))

    content = response.content.decode()
    assert water_temperature_url(bread_plan) not in content
    assert ">37 °C</span>" in content


def test_water_temperature_of_a_step_without_water_is_not_found(
    client, staff_user, planned_production_day
):
    client.force_login(staff_user)
    plan = ProductionPlan.objects.get(
        production_day=planned_production_day, product__name="Brötchen"
    )

    response = client.get(water_temperature_url(plan))

    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("is_logged_in", [False, True])
def test_water_temperature_needs_a_staff_user(client, bread_plan, method, is_logged_in):
    # Anonymous and logged in as a customer.
    if is_logged_in:
        client.force_login(UserFactory(is_staff=False))
    url = water_temperature_url(bread_plan)

    if method == "post":
        response = client.post(url, {"apply": "1"})
    else:
        response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={url}"
    bread_plan.refresh_from_db()
    assert bread_plan.temperatures == {}


@pytest.mark.parametrize(
    "posted, expected",
    [
        ({"dough_temperature": "24.5", "mixer_warming": "2"}, (24.5, 2)),
        # Empty uses the default of the settings in the production plan.
        ({"dough_temperature": "", "mixer_warming": ""}, (None, None)),
    ],
)
def test_product_form_saves_dough_temperature_and_mixer_warming(
    client, staff_user, sellable_products, settings, posted, expected
):
    settings.DOUGH_TEMPERATURE_DEFAULT = 27
    gram = UOM.objects.create(name="Gram", abbreviation="g")
    client.force_login(staff_user)
    bread = sellable_products["Bread"]
    url = reverse("workshop:product-update", kwargs={"pk": bread.pk})

    # The default is the placeholder of the empty field.
    form = client.get(url).context["form"]
    assert form["dough_temperature"].field.widget.attrs["placeholder"] == 27

    response = client.post(
        url,
        {
            "name": "Bread",
            "weight": 1000,
            "uom": gram.pk,
            "price_display": "base",
            "vat_rate": 7,
            **posted,
        },
    )

    assert response.status_code == 302
    bread.refresh_from_db()
    assert (bread.dough_temperature, bread.mixer_warming) == expected


@pytest.mark.parametrize("is_sellable", [True, False])
def test_product_detail_shows_shop_details_only_for_sellable_products(
    client, staff_user, tenant_db, is_sellable
):
    product = ProductFactory(
        name="Süßer Teig", is_sellable=is_sellable, dough_temperature=24.5
    )
    client.force_login(staff_user)

    response = client.get(reverse("workshop:product-detail", kwargs={"pk": product.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    vat = f"{product.get_vat_rate_display()}</li>"
    assert (vat in content) == is_sellable, "VAT rate only for sellable products"
    # A dough temperature that is set shows either way.
    assert "24,5 °C" in content or "24.5 °C" in content


@pytest.mark.parametrize("is_sellable", [True, False])
def test_product_form_shows_shop_fields_or_dough_fields_by_sellable(
    client, staff_user, tenant_db, is_sellable
):
    product = ProductFactory(is_sellable=is_sellable)
    client.force_login(staff_user)

    response = client.get(reverse("workshop:product-update", kwargs={"pk": product.pk}))

    content = response.content.decode()
    assert ("<div data-sellable-only hidden>" in content) == (not is_sellable)
    assert ("data-not-sellable-only hidden>" in content) == is_sellable
