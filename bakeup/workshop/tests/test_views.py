import json
from datetime import timedelta
from io import StringIO
from urllib.parse import quote

import pytest
from django.contrib.messages import get_messages
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.db.models import Sum
from django.http import QueryDict
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
    ProductMapping,
    ReminderMessage,
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
from bakeup.workshop.views import (
    get_production_day_phase,
    get_production_plan_cards,
    get_production_plan_doughs,
)


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
        # The orders pane marks it too, the delivery bill once.
        bill = response.content.decode().split('class="day-orders-print')[1]
        self.assertEqual(bill.count("badge-first-order"), 1)

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

    def groups(self):
        return get_production_plan_doughs(
            get_production_plan_cards(self.production_day)
        )

    def doughs(self):
        return [dough for group in self.groups() for dough in group["doughs"]]

    def summed(self, doughs):
        # Name, total and split of each dough, rounded to the gram.
        return [
            (
                dough["product"].name,
                round(dough["total"]),
                [(use["product"].name, round(use["weight"])) for use in dough["uses"]],
            )
            for dough in doughs
        ]

    def add_roll(self, quantity=5):
        roll = ProductFactory(
            name="Roll", category=self.categories["bread"], is_sellable=True
        )
        add(roll, self.products["sourdough"], 300)
        add(roll, self.products["wheat"], 500)
        ProductionDayProduct.objects.create(
            production_day=self.production_day, product=roll, max_quantity=quantity
        )
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )

    def test_doughs_are_the_steps_of_the_cards(self):
        # The starter inside the sourdough is a dough of its own, the deepest
        # first; the bread is its own main dough and goes nowhere else.
        self.assertEqual(
            self.summed(self.doughs()),
            [
                ("Starter", 200, [("Bread", 200)]),
                ("Sourdough", 2200, [("Bread", 2200)]),
                ("Bread", 11820, []),
            ],
        )
        sourdough = self.doughs()[1]
        self.assertEqual(
            [(row["product"].name, round(row["weight"])) for row in sourdough["rows"]],
            [("Rye flour", 1000), ("Water", 1000), ("Starter", 200)],
        )

    def test_dough_of_two_products_is_one_entry(self):
        self.add_roll()
        doughs = self.doughs()
        self.assertEqual(
            self.summed(doughs),
            [
                ("Starter", 336, [("Bread", 200), ("Roll", 136)]),
                ("Sourdough", 3700, [("Bread", 2200), ("Roll", 1500)]),
                ("Bread", 11820, []),
                ("Roll", 4000, []),
            ],
        )
        # The rows of the sourdough are summed over both products.
        self.assertEqual(
            [(row["product"].name, round(row["weight"])) for row in doughs[1]["rows"]],
            [("Rye flour", 1682), ("Water", 1682), ("Starter", 336)],
        )

    def test_doughs_come_by_category_in_bench_order(self):
        # The roll's poolish has no category, it goes last. The starter is
        # deepest, then the pre dough, then the breads themselves.
        poolish = ProductFactory(name="Poolish", weight=200)
        add(poolish, self.products["wheat"], 100)
        add(poolish, self.products["water"], 100)
        roll = ProductFactory(
            name="Roll", category=self.categories["bread"], is_sellable=True
        )
        add(roll, poolish, 200)
        add(roll, self.products["wheat"], 500)
        ProductionDayProduct.objects.create(
            production_day=self.production_day, product=roll, max_quantity=5
        )
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
        self.assertEqual(
            [
                (
                    str(group["label"]),
                    [dough["product"].name for dough in group["doughs"]],
                )
                for group in self.groups()
            ],
            [
                ("Starter", ["Starter"]),
                ("Pre dough", ["Sourdough"]),
                ("Bread", ["Bread", "Roll"]),
                ("Weitere", ["Poolish"]),
            ],
        )

    def test_doughs_scale_with_the_plan(self):
        self.add_roll(quantity=10)
        self.assertEqual(
            self.summed(self.doughs())[1],
            ("Sourdough", 5200, [("Bread", 2200), ("Roll", 3000)]),
        )

    def test_cancelled_plan_has_no_doughs(self):
        self.add_roll()
        plan = self.root()
        plan.state = ProductionPlan.State.CANCELED
        plan.save()
        self.assertEqual(
            self.summed(self.doughs()),
            [
                ("Starter", 136, [("Roll", 136)]),
                ("Sourdough", 1500, [("Roll", 1500)]),
                ("Roll", 4000, []),
            ],
        )

    def test_plan_page_shows_the_doughs(self):
        response = self.client.get(self.day_url())
        doughs = response.content.decode().split('data-view-pane="doughs" hidden>')[1]
        doughs = doughs.split('data-view-pane="ingredients"')[0]
        self.assertIn(
            '<span class="plan-dough-name">Sourdough</span>\n'
            '          <span class="plan-dough-total">2200\u00a0g</span>',
            doughs,
        )
        self.assertIn('<span class="plan-dough-name">Bread</span>', doughs)
        self.assertNotIn("<input", doughs, msg="the doughs are read only")

    def test_summary(self):
        # Pieces and weight are at the start of the plan's toolbar.
        response = self.client.get(self.day_url())
        self.assertEqual(response.context["summary"], {"pieces": 10, "weight": 10000})
        self.assertContains(
            response, '<div id="production-summary" class="section-toolbar-figures">'
        )
        figure = '<span class="toolbar-figure"><strong>{}</strong> {}</span>'
        self.assertContains(response, figure.format("10", "Stück"))
        self.assertContains(response, figure.format("10\u00a0kg", "Gesamtgewicht"))

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
        # Every hx-select-oob target of the card buttons is on the page once.
        for oob in ["production-summary", "day-actions"]:
            self.assertContains(response, f'id="{oob}"', count=1, msg_prefix=oob)
        self.assertNotContains(response, "#day-meta")
        self.assertTrue(self.root().is_canceled)
        # The only plan is canceled, the toolbar has no figures left to show.
        self.assertEqual(response.context["summary"], {"pieces": 0, "weight": 0})
        self.assertNotContains(response, 'class="toolbar-figure"')


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
        delete = [a for a in response.context["day_switch"]["actions"] if a.danger][0]
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
        # Back to the orders with the point of sale still chosen.
        self.assertRedirects(
            response,
            f"{self.detail_url()}?pickup={self.pos.pk}#orders",
            fetch_redirect_response=False,
        )
        self.assertTrue(order.positions.get().is_picked_up)

    def pane(self, response, pane, next_pane):
        content = response.content.decode()
        return content.split(f'id="{pane}"')[1].split(f'id="{next_pane}"')[0]

    def customer_order(
        self, production_day, name, quantity=3, point_of_sale=None, plan=None
    ):
        customer = User.objects.create_user(
            username=name, email=f"{name}@example.com", last_name=name
        ).customer
        order = CustomerOrder.objects.create(
            production_day=production_day,
            customer=customer,
            address="",
            point_of_sale=point_of_sale,
        )
        CustomerOrderPosition.objects.create(
            order=order,
            product=plan.product if plan else self.bread,
            quantity=quantity,
            production_plan=plan,
        )
        return order

    def orders_pane(self, response=None):
        return self.pane(response or self.detail(), "orders", "day-calendar-modal")

    def test_orders_pane_lists_only_the_orders_of_the_day(self):
        order = self.customer_order(self.production_day, "Müller")
        self.customer_order(self.next_day, "Schulz")
        pane = self.orders_pane()
        self.assertIn(
            f'href="{reverse("workshop:customer-detail", kwargs={"pk": order.customer.pk})}"',
            pane,
        )
        self.assertIn(
            f'<span class="quantity">3 x</span> <span class="position-name">{self.bread}</span>',
            pane,
        )
        self.assertNotIn("Schulz", pane)
        # The hooks of the filter: the field, one row per order, the message.
        self.assertIn('data-filter="#orders"', pane)
        self.assertEqual(pane.count("data-filter-row"), 1)
        self.assertIn("data-filter-empty", pane)

    def test_orders_pane_without_orders_offers_to_add_one(self):
        pane = self.orders_pane()
        self.assertIn("Für diesen Tag gibt es noch keine Bestellungen.", pane)
        self.assertNotIn("data-filter-row", pane)
        self.assertNotIn('data-filter="#orders"', pane)

    def test_order_rows_come_back_to_the_orders_pane(self):
        order = self.customer_order(self.production_day, "Müller")
        pane = self.orders_pane()
        next_url = quote(f"{self.detail_url()}#orders", safe="")
        for name in ["order-update", "order-delete"]:
            url = reverse(f"workshop:{name}", kwargs={"pk": order.pk})
            self.assertIn(f'href="{url}?next={next_url}"', pane, msg=name)

    def test_order_delete_returns_to_next(self):
        order = self.customer_order(self.production_day, "Müller")
        next_url = f"{self.detail_url()}#orders"
        response = self.client.post(
            reverse("workshop:order-delete", kwargs={"pk": order.pk})
            + "?next="
            + quote(next_url, safe="")
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.assertFalse(CustomerOrder.objects.filter(pk=order.pk).exists())

    def test_order_add_returns_to_next(self):
        customer = User.objects.create_user(
            username="neu", email="neu@example.com"
        ).customer
        next_url = f"{self.detail_url()}#orders"
        url = reverse(
            "workshop:order-add", kwargs={"production_day": self.production_day.pk}
        )
        response = self.client.post(
            f"{url}?next={quote(next_url, safe='')}",
            {
                "customer": customer.pk,
                "production_day": self.production_day.pk,
                "form-TOTAL_FORMS": 0,
                "form-INITIAL_FORMS": 0,
                "content": "",
            },
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        self.assertEqual(
            list(
                CustomerOrder.objects.filter(
                    production_day=self.production_day
                ).values_list("customer", flat=True)
            ),
            [customer.pk],
        )

    def test_order_actions_come_back_to_the_orders_pane(self):
        pk = self.production_day.pk
        actions = self.detail().context["orders_actions"]
        next_url = "?next=" + quote(f"{self.detail_url()}#orders", safe="/")
        self.assertEqual([a.url for a in actions.buttons if a.url], [])
        self.assertEqual(
            [a.url for a in actions.menu if a.url],
            [
                reverse("workshop:order-add", kwargs={"production_day": pk}) + next_url,
                reverse("workshop:order-batch", kwargs={"pk": pk}) + next_url,
                reverse(
                    "workshop:production-day-order-max-quantities", kwargs={"pk": pk}
                ),
                reverse("workshop:order-list") + f"?production_day={pk}",
            ],
        )

    def test_order_max_quantities_returns_to_the_orders(self):
        response = self.client.post(
            reverse(
                "workshop:production-day-order-max-quantities",
                kwargs={"pk": self.production_day.pk},
            )
        )
        self.assertRedirects(
            response, f"{self.detail_url()}#orders", fetch_redirect_response=False
        )

    def test_all_picked_up_returns_to_the_orders(self):
        order = self.add_order()
        response = self.client.get(
            reverse(
                "workshop:production-day-all-picked-up",
                kwargs={"pk": self.production_day.pk},
            )
        )
        self.assertRedirects(
            response, f"{self.detail_url()}#orders", fetch_redirect_response=False
        )
        self.assertTrue(order.positions.get().is_picked_up)

    def test_overview_shows_the_day(self):
        self.add_order()
        self.production_day.point_of_sales.add(self.pos)
        overview = self.pane(self.detail(), "overview", "orders")
        self.assertNotIn("day-info-description", overview)
        self.assertIn("<dd>Market</dd>", overview)
        # Orders, then the ordered pieces, nothing is published in the shop.
        self.assertEqual(
            [part.split("</dd>")[0] for part in overview.split("<dd>")[2:4]],
            ["1", "3"],
        )
        self.assertNotIn("Im Shop verkauft", overview)
        self.production_day.description = "Mit Weihnachtsstollen & Co."
        self.production_day.save()
        overview = self.pane(self.detail(), "overview", "orders")
        self.assertIn(
            '<p class="day-info-description">Mit Weihnachtsstollen &amp; Co.</p>',
            overview,
        )

    def test_product_table_carries_its_totals(self):
        # Bread is overbooked: 12 of 10, the cake has no orders.
        self.add_order()
        order = CustomerOrder.objects.get()
        order.positions.update(quantity=12)
        response = self.detail()
        self.assertEqual(
            response.context["product_totals"],
            {"count": 2, "ordered": 12, "max": 20, "percent": 60, "is_over": False},
        )
        self.assertContains(response, "2 Produkte</th>")
        self.assertContains(response, '<span class="fill-value">12 / 20</span>')

    def test_marking_a_point_runs_in_place_and_toggles(self):
        # From the menu with htmx: the page comes back by the redirect, a
        # second time unmarks the point again.
        order = self.add_order()
        url = reverse(
            "workshop:pos-all-picked-up",
            kwargs={"production_day": self.production_day.pk, "pos": self.pos.pk},
        )
        response = self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(order.positions.get().is_picked_up)
        self.client.post(url, HTTP_HX_REQUEST="true")
        self.assertFalse(order.positions.get().is_picked_up)

    def add_plain_roll(self):
        roll = ProductFactory(
            name="Roll", category=self.categories["bread"], is_sellable=True
        )
        add(roll, self.products["wheat"], 500)
        ProductionDayProduct.objects.create(
            production_day=self.production_day, product=roll, max_quantity=5
        )
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
        return self.root(roll)

    def set_roots(self, state):
        ProductionPlan.objects.filter(
            production_day=self.production_day, parent_plan=None
        ).update(state=state)

    def test_phase_follows_the_plans(self):
        empty = ProductionDay.objects.create(
            day_of_sale=self.next_day.day_of_sale + timedelta(1)
        )
        self.assertEqual(get_production_day_phase(empty), "collecting")
        self.assertEqual(get_production_day_phase(self.production_day), "collecting")
        self.set_roots(ProductionPlan.State.CANCELED)
        self.assertEqual(get_production_day_phase(self.production_day), "collecting")
        self.set_roots(ProductionPlan.State.PRODUCED)
        self.assertEqual(get_production_day_phase(self.production_day), "handing_out")
        # One started product among planned ones is enough.
        roll = self.add_plain_roll()
        self.set_roots(ProductionPlan.State.PLANNED)
        roll.set_production()
        self.assertEqual(get_production_day_phase(self.production_day), "handing_out")

    def orders_toolbar(self, response):
        actions = response.context["orders_actions"]
        return (
            [str(a.label) for a in actions.buttons],
            [(str(a.label), a.pickup) for a in actions.menu],
        )

    def test_collecting_is_about_editing_the_orders(self):
        order = self.add_order()
        response = self.detail()
        self.assertEqual(response.context["phase"], "collecting")
        self.assertEqual(
            self.orders_toolbar(response),
            (
                ["Lieferschein drucken"],
                [
                    ("Bestellung hinzufügen", ""),
                    ("Ändere Bestellungen", ""),
                    ("max. Menge bestellen", ""),
                    ("In Bestellliste anzeigen", ""),
                ],
            ),
        )
        pane = self.orders_pane(response)
        self.assertNotIn("day-order-tick", pane)
        self.assertNotIn("Abgeholt</th>", pane.split("day-orders-print")[0])
        self.assertNotIn("section-hint", pane)
        self.assertIn(reverse("workshop:order-update", kwargs={"pk": order.pk}), pane)

    def test_handing_out_is_about_packing_and_picking_up(self):
        self.add_order()
        self.start_day()
        response = self.detail()
        self.assertEqual(response.context["phase"], "handing_out")
        self.assertEqual(
            self.orders_toolbar(response),
            (
                ["Lieferschein drucken"],
                [
                    ("Bestellung hinzufügen", ""),
                    ("Ändere Bestellungen", ""),
                    ("In Bestellliste anzeigen", ""),
                    ("Alle als abgeholt markieren", "all"),
                    ("Alle als abgeholt markieren", str(self.pos.pk)),
                ],
            ),
        )
        pane = self.orders_pane(response)
        self.assertEqual(pane.count('class="text-center day-order-tick"'), 1)
        self.assertIn(
            "Produktion läuft – Bestellungen der gestarteten Produkte sind gesperrt.",
            pane,
        )
        # The packing list of all points while handing out.
        self.assertIn('data-pickup-only="all"', pane)

    def test_only_unlocked_orders_can_be_edited_while_handing_out(self):
        # A mixed day: the bread is started, the roll still planned.
        roll = self.add_plain_roll()
        self.pos = PointOfSale.objects.create(name="Market")
        locked = self.customer_order(
            self.production_day, "Brot", point_of_sale=self.pos, plan=self.root()
        )
        open_order = self.customer_order(
            self.production_day, "Semmel", point_of_sale=self.pos, plan=roll
        )
        self.start()
        pane = self.orders_pane()
        for order, editable in [(locked, False), (open_order, True)]:
            url = reverse("workshop:order-update", kwargs={"pk": order.pk})
            self.assertEqual(url in pane, editable, msg=order.customer)

    def test_orders_come_by_point_of_sale_and_customer(self):
        north = PointOfSale.objects.create(name="Nord", short_name="N")
        south = PointOfSale.objects.create(name="Süd")
        # A point without orders this day gets no chip.
        unused = PointOfSale.objects.create(name="Leer")
        self.production_day.point_of_sales.add(unused)
        for name, point in [
            ("Zander", north),
            ("Adler", south),
            ("Bauer", north),
            ("Ohne", None),
        ]:
            self.customer_order(self.production_day, name, point_of_sale=point)
        response = self.detail()
        self.assertEqual(
            [
                (
                    str(group["label"]),
                    [o.customer.user.last_name for o in group["orders"]],
                )
                for group in response.context["order_groups"]
            ],
            [
                ("Nord", ["Bauer", "Zander"]),
                ("Süd", ["Adler"]),
                ("Ohne Abholstelle", ["Ohne"]),
            ],
        )
        pane = self.orders_pane(response)
        chips = [part.split('"')[0] for part in pane.split('data-pickup-chip="')[1:]]
        self.assertEqual(chips, ["", str(north.pk), str(south.pk), "none"])
        self.assertIn(
            f'data-pickup-chip="{north.pk}" aria-pressed="false">N '
            '<span class="pickup-chip-count">2</span>',
            pane,
        )

    def test_each_point_has_its_products_and_its_printed_bill(self):
        north = PointOfSale.objects.create(name="Nord")
        south = PointOfSale.objects.create(name="Süd")
        self.customer_order(
            self.production_day, "Bauer", 3, point_of_sale=north, plan=self.root()
        )
        self.customer_order(
            self.production_day, "Zander", 2, point_of_sale=north, plan=self.root()
        )
        self.customer_order(
            self.production_day, "Adler", 1, point_of_sale=south, plan=self.root()
        )
        response = self.detail()
        self.assertEqual(
            {
                str(group["label"]): list(group["summary"])
                for group in response.context["order_groups"]
            },
            {
                "Nord": [{"product__name": "Bread", "quantity": 5}],
                "Süd": [{"product__name": "Bread", "quantity": 1}],
            },
        )
        pane = self.orders_pane(response)
        # Every point of sale is a card of its own, with what goes there in
        # total on top of its orders.
        cards = pane.split('class="day-orders-print')[0].split("day-orders-card ")[1:]
        self.assertEqual(
            [card.split('data-pickup="')[1].split('"')[0] for card in cards],
            [str(north.pk), str(south.pk)],
        )
        self.assertIn(
            '<span class="delivery-bill-summary-qty">5 ×</span> Bread', cards[0]
        )
        self.assertIn(
            '<span class="delivery-bill-summary-qty">1 ×</span> Bread', cards[1]
        )
        self.assertIn("Bauer", cards[0])
        self.assertNotIn("Adler", cards[0])
        # The delivery bill is in the page for print, all points of sale.
        printed = pane.split('class="day-orders-print d-none d-print-block"')[1]
        self.assertEqual(
            [part.split('"')[0] for part in printed.split('data-pickup-section="')[1:]],
            [str(north.pk), str(south.pk)],
        )

    def test_many_points_of_sale_are_a_dropdown(self):
        # Up to six points of sale are chips, more are a dropdown.
        points = [PointOfSale.objects.create(name=f"Point {n}") for n in range(7)]
        for number, point in enumerate(points[:6]):
            self.customer_order(
                self.production_day,
                f"Bauer{number}",
                1,
                point_of_sale=point,
                plan=self.root(),
            )
        pane = self.orders_pane(self.detail())
        self.assertEqual(pane.count("data-pickup-chip="), 7, "six points and all")
        self.assertNotIn("data-pickup-select", pane)
        self.customer_order(
            self.production_day, "Zander", 2, point_of_sale=points[6], plan=self.root()
        )
        pane = self.orders_pane(self.detail())
        self.assertNotIn("data-pickup-chip=", pane)
        self.assertIn('<option value="">Alle Abholstellen (7)</option>', pane)
        self.assertIn(f'<option value="{points[6].pk}">Point 6 (1)</option>', pane)

    def test_delivery_bill_is_no_tab_of_its_own(self):
        response = self.detail()
        keys = [tab["key"] for tab in response.context["day_switch"]["tabs"]]
        self.assertNotIn("delivery-bill", keys)
        self.assertNotContains(response, 'id="delivery-bill"')


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

    def test_overlay_is_the_calendar_alone_and_links_to_the_plan(self):
        day = self.production_day.day_of_sale
        params = {"overlay": 1, "link": "plan", "selected": day.isoformat()}
        response = self.calendar(month=day.strftime("%Y-%m"), **params)
        self.assertTemplateNotUsed(response, "workshop/base.html")
        calendar = response.context["calendar"]
        cell = self.cells(response)[day]
        self.assertTrue(cell["is_selected"])
        self.assertEqual(cell["url"], self.day_url())
        self.assertContains(response, 'hx-target="#production-day"')
        # Month, week and the arrows stay in the layer, section and day.
        for key in ["previous_url", "next_url", "month_view_url", "week_view_url"]:
            query = QueryDict(calendar[key].split("?")[1])
            self.assertEqual(
                {name: query[name] for name in params},
                {name: str(value) for name, value in params.items()},
                msg=key,
            )
        # Only choosing a day changes the URL of the page behind the layer.
        days = [cell for cell in self.cells(response).values() if cell["day"]]
        self.assertContains(response, "hx-push-url", count=len(days))
        # Adding a day belongs to the day pages.
        self.assertNotContains(response, reverse("workshop:production-day-add"))

    def test_close_button_only_in_the_layer(self):
        day = self.production_day.day_of_sale
        close = 'class="btn-close day-calendar-close" data-bs-dismiss="modal"'
        overlay = self.calendar(
            month=day.strftime("%Y-%m"), overlay=1, link="day", selected=day
        )
        self.assertContains(overlay, close, count=1)
        self.assertNotContains(self.calendar(month=day.strftime("%Y-%m")), close)

    def test_every_day_page_loads_its_layer_in_advance(self):
        for link, url in self.section_urls().items():
            with self.subTest(link=link):
                response = self.client.get(url)
                overlay_url = response.context["day_switch"]["week"]["overlay_url"]
                self.assertIn(f"link={link}", overlay_url)
                self.assertContains(
                    response,
                    f'<div class="day-calendar-loader" hidden hx-get="{overlay_url}"'
                    ' hx-target="#day-calendar-modal-body"'.replace("&", "&amp;"),
                )
                # The date button only opens the layer.
                self.assertNotContains(
                    response, 'hx-target="#day-calendar-modal-body">'
                )

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

    def section_urls(self, production_day=None):
        production_day = production_day or self.production_day
        return {
            "day": self.detail_url(production_day),
            "plan": self.url("production-plan-production-day", production_day.pk),
            "reminder": reverse(
                "workshop:production-day-reminder",
                kwargs={"production_day": production_day.pk},
            ),
        }

    def test_other_days_lead_back_to_the_current_day(self):
        current = ProductionDay.objects.upcoming().first()
        other = next(
            day
            for day in (self.prev_day, self.production_day, self.next_day)
            if day != current
        )
        for link, url in self.section_urls(other).items():
            with self.subTest(link=link):
                response = self.client.get(url)
                current_url = self.section_urls(current)[link]
                self.assertEqual(
                    response.context["day_switch"]["current_url"], current_url
                )
                self.assertContains(
                    response,
                    f'class="day-title-current" href="{current_url}"',
                )
        response = self.client.get(self.section_urls(current)["day"])
        self.assertIsNone(response.context["day_switch"]["current_url"])
        self.assertNotContains(response, "day-title-current")

    def test_strip_keeps_the_section_on_every_day_page(self):
        day = self.production_day.day_of_sale
        monday = day - timedelta(days=day.weekday())
        # The neighbours of the day that are in its week.
        others = [
            other
            for other in (self.prev_day, self.next_day)
            if 0 <= (other.day_of_sale - monday).days < 7
        ]
        self.assertTrue(others)
        for link, url in self.section_urls().items():
            with self.subTest(link=link):
                response = self.client.get(url)
                strip = response.context["day_switch"]["week"]
                cells = {cell["date"]: cell for cell in strip["weeks"][0]}
                self.assertEqual(
                    list(cells), [monday + timedelta(days=n) for n in range(7)]
                )
                self.assertEqual(
                    [date for date, cell in cells.items() if cell["is_selected"]],
                    [day],
                )
                for other in others:
                    other_url = self.section_urls(other)[link]
                    self.assertEqual(cells[other.day_of_sale]["url"], other_url)
                    self.assertContains(response, f'href="{other_url}"')
                self.assertContains(response, 'id="day-calendar-modal"', count=1)
                self.assertContains(
                    response, f'hx-get="{strip["overlay_url"]}"'.replace("&", "&amp;")
                )

    def test_plan_tab_is_checked_once_everything_is_produced(self):
        def badge():
            tabs = self.detail().context["day_switch"]["tabs"]
            return [tab.get("badge") for tab in tabs if tab["key"] == "plan"][0]

        plan = self.root()
        self.assertIsNone(badge())
        # In production isn't produced yet.
        plan.set_production()
        self.assertIsNone(badge())
        plan.state = ProductionPlan.State.PRODUCED
        plan.save()
        self.assertEqual(badge(), "✓")
        # A cancelled plan beside it doesn't hold the check back.
        ProductionPlan.objects.create(
            production_day=self.production_day,
            product=Product.duplicate(self.cake),
            quantity=10,
            state=ProductionPlan.State.CANCELED,
        )
        self.assertEqual(badge(), "✓")
        # Only cancelled plans are nothing produced.
        plan.state = ProductionPlan.State.CANCELED
        plan.save()
        self.assertIsNone(badge())

    def test_tabs_keep_the_day_on_every_day_page(self):
        self.add_order()
        urls = self.section_urls()
        day_url = urls["day"]
        for link, url in urls.items():
            with self.subTest(link=link):
                tabs = self.client.get(url).context["day_switch"]["tabs"]
                self.assertEqual(
                    [(tab["key"], tab["url"]) for tab in tabs],
                    [
                        ("overview", f"{day_url}#overview"),
                        ("orders", f"{day_url}#orders"),
                        ("plan", urls["plan"]),
                        ("reminder", urls["reminder"]),
                    ],
                )
                active = "overview" if link == "day" else link
                self.assertEqual(
                    [tab["key"] for tab in tabs if tab.get("is_active")], [active]
                )
                # Only the day page switches its two panes in place, the
                # ingredients are a view of the plan, the delivery bill is
                # printed from the orders.
                panes = ["overview", "orders"]
                self.assertEqual(
                    [tab["key"] for tab in tabs if tab.get("is_pane")],
                    panes if link == "day" else [],
                )
                # Day page and plan swap into each other, the emails load.
                swaps = {
                    "day": {"plan": urls["plan"]},
                    "plan": dict.fromkeys(panes, day_url),
                    "reminder": {},
                }[link]
                self.assertEqual(
                    {tab["key"]: tab["swap_url"] for tab in tabs if "swap_url" in tab},
                    swaps,
                )
                # Only the orders carry their number.
                self.assertEqual(
                    {tab["key"]: tab["badge"] for tab in tabs if "badge" in tab},
                    {"orders": 1},
                )

    def test_tab_row_links_and_panes(self):
        urls = self.section_urls()
        response = self.detail()
        self.assertContains(response, 'data-bs-target="#orders"')
        self.assertContains(response, f'class="nav-link" href="{urls["plan"]}"')
        response = self.client.get(urls["plan"])
        self.assertNotContains(response, 'data-bs-target="#orders"')
        self.assertContains(
            response,
            f'data-day-pane="orders" hx-get="{urls["day"]}" hx-target="#day-page"',
        )
        self.assertContains(response, 'id="day-page"', count=1)
        self.assertContains(response, f'class="nav-link" href="{urls["day"]}#orders"')
        self.assertContains(response, f'class="nav-link active" href="{urls["plan"]}"')

    def test_plan_has_a_view_of_its_ingredients(self):
        response = self.client.get(self.day_url())
        self.assertEqual(
            [view["key"] for view in response.context["plan_views"]],
            ["plan", "doughs", "ingredients"],
        )
        # The switch, the plan shown first, the ingredients hidden.
        self.assertContains(
            response,
            '<button type="button" class="btn btn-surface active" data-view="plan"'
            ' aria-pressed="true">Plan</button>',
        )
        self.assertContains(
            response,
            '<button type="button" class="btn btn-surface" data-view="ingredients"'
            ' aria-pressed="false">Zutaten</button>',
        )
        content = response.content.decode()
        plan = content.split('data-view-pane="plan">')[1].split("data-view-pane=")[0]
        ingredients = content.split('data-view-pane="ingredients" hidden>')[1]
        # Each view brings its own print heading, a card keeps its deep link.
        self.assertIn("Produktionsplan", plan.split("</h2>")[0])
        self.assertIn(f'id="card-{self.day_products[self.bread.pk].pk}"', plan)
        self.assertIn("Zusammenfassung Zutaten", ingredients.split("</h3>")[0])
        table = ingredients.split("</table>")[0]
        self.assertIn("<td>Rye flour</td>", table)
        self.assertIn('<td class="text-end">1100 g</td>', table)
        # One print button for whichever view is on screen.
        self.assertContains(response, "data-print", count=1)

    def test_ingredients_are_no_longer_a_pane_of_the_day(self):
        response = self.detail()
        self.assertNotContains(response, 'id="ingredients"')
        self.assertNotContains(response, "day-ingredients")

    def test_plan_page_starts_and_finishes_all_in_place(self):
        pk = self.production_day.pk
        start = reverse(
            "workshop:production-plans-start", kwargs={"production_day": pk}
        )
        finish = reverse(
            "workshop:production-plans-finish", kwargs={"production_day": pk}
        )
        response = self.client.get(self.day_url())
        self.assertContains(response, f'hx-post="{start}?next={self.day_url()}"')
        self.assertNotContains(response, finish)
        self.start_day()
        response = self.client.get(self.day_url())
        self.assertContains(response, f'hx-post="{finish}?next={self.day_url()}"')
        self.assertNotContains(response, start)
        self.assertContains(response, 'id="wake-lock-toggle"')

    def test_same_head_actions_on_every_day_page(self):
        pk = self.production_day.pk
        day = {"production_day": pk}
        start = reverse("workshop:production-plans-start", kwargs=day)
        finish = reverse("workshop:production-plans-finish", kwargs=day)
        (update,) = self.day_urls("production-day-update")
        urls = self.section_urls()
        menu = ["Neuer Produktionstag", "Kopieren", "Abos", "Exportieren als CSV"]
        menu.append("Löschen")
        for step, label, url in [
            (start, "Alle starten", None),
            (finish, "Alle fertigstellen", "started"),
        ]:
            if url:
                self.start_day()
            for link, page_url in urls.items():
                with self.subTest(link=link, step=label):
                    response = self.client.get(page_url)
                    actions = response.context["day_switch"]["actions"]
                    # Editing is quiet, the next step the one filled button,
                    # the rest in the menu. All come back to this page.
                    self.assertEqual(
                        [(str(a.label), a.kind) for a in actions.buttons],
                        [("Bearbeiten", "secondary"), (label, "primary")],
                    )
                    self.assertEqual([str(a.label) for a in actions.menu], menu)
                    self.assertEqual(
                        [a.url for a in actions.buttons],
                        [f"{update}?next={page_url}", f"{step}?next={page_url}"],
                    )
                    # In place where the page has a swap target, the pickup
                    # emails load.
                    target = response.context["day_switch"]["target"]
                    if target:
                        self.assertContains(
                            response,
                            f'hx-post="{step}?next={page_url}" hx-target="{target}"',
                        )
                    else:
                        self.assertContains(response, f'href="{step}?next={page_url}"')
                        self.assertNotContains(response, f'hx-post="{step}')

    def test_finish_waits_in_the_menu_while_plans_are_left_to_start(self):
        pk = self.production_day.pk
        roll = ProductFactory(
            name="Roll", category=self.categories["bread"], is_sellable=True
        )
        add(roll, self.products["wheat"], 500)
        ProductionDayProduct.objects.create(
            production_day=self.production_day, product=roll, max_quantity=5
        )
        self.production_day.create_or_update_production_plans(
            state=ProductionPlan.State.PLANNED, create_max_quantity=True
        )
        self.start()
        actions = self.client.get(self.day_url()).context["day_switch"]["actions"]
        self.assertEqual(
            [a.url for a in actions.buttons if a.kind == "primary"],
            [
                reverse(
                    "workshop:production-plans-start", kwargs={"production_day": pk}
                )
                + f"?next={self.day_url()}"
            ],
        )
        self.assertIn(
            reverse("workshop:production-plans-finish", kwargs={"production_day": pk})
            + f"?next={self.day_url()}",
            [a.url for a in actions.menu],
        )

    def test_sidebar_entry_of_the_day_pages(self):
        days = reverse("workshop:production-day-next")
        plans = reverse("workshop:production-plan-next")
        pages = {
            **self.section_urls(),
            "calendar": self.calendar().request["PATH_INFO"],
        }
        for name, url in pages.items():
            with self.subTest(page=name):
                response = self.client.get(url)
                # The plan of a day has its own entry, the other pages of a
                # day belong to the production days.
                active, other = (plans, days) if name == "plan" else (days, plans)
                self.assertContains(
                    response, f'aria-current="page" href="{active}"', count=1
                )
                self.assertContains(response, f'class="nav-link" href="{other}"')
                self.assertContains(response, "Produktionstage</span>")
                self.assertContains(response, "Produktionspläne</span>")
                self.assertNotContains(
                    response,
                    f'href="{reverse("workshop:production-day-reminder-next")}"',
                )
                self.assertNotContains(
                    response,
                    f'class="nav-link" href="{reverse("workshop:production-day-calendar")}"',
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
        self.assertFalse(switch["week"]["can_add_day"])
        # The strip adds no day here, a new day is only in the ⋯ menu.
        self.assertNotContains(
            response, reverse("workshop:production-day-add") + "?day_of_sale="
        )


class PickupEmailsEditorTest(PickupEmailsViewTest):
    def body(self, text="Hallo {{ last_name }}"):
        return json.dumps(
            {
                "blocks": [
                    {
                        "key": "a",
                        "type": "unstyled",
                        "text": text,
                        "depth": 0,
                        "inlineStyleRanges": [],
                        "entityRanges": [],
                    }
                ],
                "entityMap": {},
            }
        )

    def mail_url(self, name, **kwargs):
        return reverse(
            f"workshop:production-day-reminder-{name}",
            kwargs={"production_day": self.production_day.pk, **kwargs},
        )

    def new_url(self, query=""):
        return f"{self.reminder_url()}?new=1{query}#reminder-editor"

    def edit_url(self, mail):
        return f"{self.reminder_url()}?edit={mail.pk}#reminder-editor"

    def page(self, **params):
        response = self.client.get(self.reminder_url(), params)
        self.assertEqual(response.status_code, 200)
        return response

    def post(self, **data):
        return self.client.post(self.reminder_url(), data)

    def write(self, action="save", mail=None, subject="Abholung", points=(), **data):
        # The editor of a new email, or of the draft mail: to all orders
        # without points.
        return self.client.post(
            self.reminder_url(),
            {
                "editor": mail.pk if mail else "new",
                "recipients": "points" if points else "all",
                "points": [str(point) for point in points],
                "subject": subject,
                "body": self.body(),
                action: "",
                **data,
            },
        )

    def make_draft(self, points=(), without=False, **fields):
        mail = ReminderMessage.objects.create(
            production_day=self.production_day,
            subject=fields.pop("subject", "Entwurf"),
            body="<p>Hallo {{ last_name }}</p>",
            without_point_of_sale=without,
            **fields,
        )
        mail.points_of_sale.set(points)
        return mail

    def deliver(self):
        # What the command send_reminder_emails does with the queued mails.
        call_command("send_reminder_emails", stdout=StringIO())

    def two_points(self):
        self.north = PointOfSale.objects.create(name="Nord", short_name="N")
        self.south = PointOfSale.objects.create(name="Süd")
        self.customer_order(self.production_day, "Müller", point_of_sale=self.north)
        self.customer_order(self.production_day, "Meier", point_of_sale=self.south)
        self.customer_order(self.production_day, "Schulze", point_of_sale=self.south)

    def recipients(self):
        return sorted(address for message in mail.outbox for address in message.to)

    def queued_orders(self):
        mail = ReminderMessage.objects.get(state=ReminderMessage.State.PLANNED_SENDING)
        return sorted(mail.orders.values_list("customer__user__last_name", flat=True))

    def mail_rows(self, response=None):
        return [
            (mail.subject, mail.recipients_label, len(mail.recipients), mail.state)
            for mail in (response or self.page()).context["overview"]["mails"]
        ]

    def point_chips(self, response=None):
        return [
            (point["short_name"], point["orders"], point["open"], point.get("url"))
            for point in (response or self.page()).context["overview"]["points"]
        ]

    def test_empty_day_shows_an_empty_table_and_the_new_email_button(self):
        page = self.page()
        self.assertEqual(page.context["overview"]["mails"], [])
        self.assertContains(
            page,
            '<p class="reminder-empty-title">Noch keine E-Mails für diesen Tag.</p>',
        )
        self.assertContains(
            page,
            f'<a class="btn btn-surface btn-sm" href="{self.new_url()}" data-reminder-new>',
        )
        # "New email" opens the editor that is on the page already, hidden.
        self.assertEqual(
            [(action.id, action.url) for action in page.context["reminder_actions"]],
            [("reminder-new", self.new_url())],
        )
        self.assertFalse(page.context["editor"]["is_open"])
        self.assertContains(page, 'data-mode="new" hidden>')

    def test_status_line_counts_the_notified_orders_per_point_of_sale(self):
        self.two_points()
        self.customer_order(self.production_day, "Ohne")
        page = self.page()
        self.assertContains(page, "0 von 4 Bestellungen benachrichtigt")
        new = f"{self.reminder_url()}?new=1"
        self.assertEqual(
            self.point_chips(page),
            [
                ("N", 1, 1, f"{new}&points={self.north.pk}#reminder-editor"),
                ("Süd", 2, 2, f"{new}&points={self.south.pk}#reminder-editor"),
                ("Ohne Abholstelle", 1, 1, f"{new}&points=none#reminder-editor"),
            ],
        )
        # The chip opens the editor in place with its point chosen.
        self.assertContains(
            page, f'data-reminder-new data-points="{self.north.pk}" title='
        )
        self.write("send", points=[self.south.pk])
        self.customer_order(self.production_day, "Neu", point_of_sale=self.south)
        page = self.page()
        self.assertContains(page, "2 von 5 Bestellungen benachrichtigt")
        # Süd got an email, its new order is open: a new email to it only
        # goes to the orders without one.
        self.assertEqual(
            self.point_chips(page),
            [
                ("N", 1, 1, f"{new}&points={self.north.pk}#reminder-editor"),
                ("Süd", 3, 1, f"{new}&points={self.south.pk}#reminder-editor"),
                ("Ohne Abholstelle", 1, 1, f"{new}&points=none#reminder-editor"),
            ],
        )
        self.assertContains(
            page,
            f'data-reminder-new data-points="{self.south.pk}" title=',
        )

    def test_a_point_notified_by_a_mail_from_before_is_done(self):
        # A mail from before the orders were kept went to its point.
        self.two_points()
        ReminderMessage.objects.create(
            production_day=self.production_day,
            point_of_sale=self.south,
            subject="Alt",
            body="",
            state=ReminderMessage.State.SENT,
            send_log=["Meier@example.com", "Schulze@example.com"],
            sent_date=timezone.now(),
        )
        page = self.page()
        self.assertEqual(
            self.point_chips(page),
            [
                ("N", 1, 1, self.new_url(f"&points={self.north.pk}")),
                ("Süd", 2, 0, None),
            ],
        )
        self.assertEqual(
            self.mail_rows(page), [("Alt", "Süd", 2, ReminderMessage.State.SENT)]
        )

    def test_new_email_starts_with_the_standard_text_to_all_orders(self):
        self.two_points()
        # Hidden on the page, open with ?new=1 (the links without JavaScript).
        self.assertFalse(self.page().context["editor"]["is_open"])
        response = self.page(new="1")
        editor = response.context["editor"]
        self.assertTrue(editor["is_open"])
        form = editor["form"]
        self.assertEqual(
            (form["recipients"].value(), form["points"].value()), ("all", [])
        )
        self.assertEqual(
            form["subject"].value(), "[{{site_name}}] Deine Bestellung ist abholbereit"
        )
        self.assertEqual(
            [(point["name"], point["orders"]) for point in editor["points"]],
            [("Nord", 1), ("Süd", 2)],
        )
        self.assertContains(response, "An 3 Bestellungen senden")

    def test_new_email_from_a_chip_chooses_its_point(self):
        self.two_points()
        self.write("send", points=[self.north.pk])
        response = self.page(new="1", points=self.south.pk)
        form = response.context["editor"]["form"]
        self.assertEqual(
            (form["recipients"].value(), form["points"].value()),
            ("points", [str(self.south.pk)]),
        )
        self.assertContains(response, "An 2 Bestellungen senden")

    def test_a_draft_keeps_who_it_is_for_and_reaches_later_orders(self):
        self.two_points()
        response = self.write(subject="Morgens", points=[self.south.pk])
        self.assertRedirects(response, self.reminder_url())
        draft = ReminderMessage.objects.get()
        self.assertEqual(
            (
                draft.state,
                list(draft.points_of_sale.all()),
                draft.without_point_of_sale,
                list(draft.orders.all()),
            ),
            (ReminderMessage.State.PLANNED, [self.south], False, []),
        )
        self.assertEqual(
            self.mail_rows(), [("Morgens", "Süd", 2, ReminderMessage.State.PLANNED)]
        )
        # An order that comes in later is in when the draft is sent.
        self.customer_order(self.production_day, "Neu", point_of_sale=self.south)
        self.assertEqual(
            self.mail_rows(), [("Morgens", "Süd", 3, ReminderMessage.State.PLANNED)]
        )
        response = self.post(send=draft.pk)
        self.assertRedirects(response, self.reminder_url())
        self.assertEqual(self.queued_orders(), ["Meier", "Neu", "Schulze"])
        self.deliver()
        self.assertEqual(
            self.recipients(),
            ["Meier@example.com", "Neu@example.com", "Schulze@example.com"],
        )
        draft.refresh_from_db()
        self.assertEqual(draft.state, ReminderMessage.State.SENT)

    def test_the_list_sends_a_draft_from_under_its_preview(self):
        self.two_points()
        draft = self.make_draft(points=[self.north])
        page = self.page()
        self.assertContains(
            page,
            f'data-reminder-preview-open aria-controls="reminder-mail-{draft.pk}"',
        )
        self.assertContains(
            page,
            f'form="reminder-send-form" name="send" value="{draft.pk}"><i class="fas'
            ' fa-paper-plane" aria-hidden="true"></i> An 1 Bestellung senden',
        )

    def test_sending_from_the_editor_goes_to_the_chosen_recipients(self):
        self.two_points()
        self.customer_order(self.production_day, "Ohne")
        cases = [
            ({}, ["Meier", "Müller", "Ohne", "Schulze"]),
            ({"points": [self.north.pk, "none"]}, ["Müller", "Ohne"]),
            ({"points": [self.south.pk]}, ["Meier", "Schulze"]),
        ]
        for data, expected in cases:
            with self.subTest(data=data):
                ReminderMessage.objects.all().delete()
                response = self.write("send", **data)
                self.assertRedirects(response, self.reminder_url())
                self.assertEqual(self.queued_orders(), expected)

    def test_sending_to_nobody_is_refused(self):
        self.two_points()
        CustomerOrder.objects.filter(production_day=self.production_day).delete()
        response = self.write("send", subject="Noch mal")
        self.assertEqual(response.status_code, 200)
        # The page again, with the editor open and what was written in it.
        editor = response.context["editor"]
        self.assertEqual(
            (editor["is_open"], editor["mail"], editor["form"]["subject"].value()),
            (True, None, "Noch mal"),
        )
        self.assertEqual(
            editor["form"].non_field_errors(),
            ["Niemand bekommt diese E-Mail, wähle andere Empfänger."],
        )
        self.assertFalse(ReminderMessage.objects.filter(subject="Noch mal").exists())

    def test_single_points_need_a_point(self):
        self.two_points()
        response = self.write(recipients="points")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["editor"]["is_open"])
        self.assertEqual(
            response.context["editor"]["form"].errors,
            {"points": ["Wähle mindestens eine Abholstelle."]},
        )
        self.assertFalse(ReminderMessage.objects.exists())

    def test_editing_a_draft_changes_text_and_recipients(self):
        self.two_points()
        draft = self.make_draft(points=[self.north], subject="Erst")
        self.make_draft(subject="Andere")
        page = self.page(edit=draft.pk)
        editor = page.context["editor"]
        form = editor["form"]
        self.assertEqual((editor["mail"], editor["is_open"]), (draft, True))
        # The one editor of the page is under the row of the draft, "New
        # email" loads the page with the editor of a new one.
        html = page.content.decode()
        self.assertEqual(html.count('id="reminder-editor"'), 1)
        self.assertIn(
            'id="reminder-editor"', html.split(f'id="reminder-row-{draft.pk}"')[1]
        )
        self.assertContains(page, f'href="{self.new_url()}" class="btn btn-primary"')
        self.assertEqual(
            (
                form["recipients"].value(),
                form["points"].value(),
                form["subject"].value(),
            ),
            ("points", [str(self.north.pk)], "Erst"),
        )
        # An error shows the editor under its row again.
        response = self.write(mail=draft, subject="", points=[self.south.pk])
        self.assertEqual(
            (
                response.context["editor"]["mail"],
                response.context["editor"]["form"].errors,
            ),
            (draft, {"subject": ["Dieses Feld muss ausgefüllt werden."]}),
        )
        response = self.write(mail=draft, subject="Dann", points=[self.south.pk])
        self.assertRedirects(response, self.reminder_url())
        draft.refresh_from_db()
        self.assertEqual(
            (draft.subject, list(draft.points_of_sale.all()), draft.state),
            ("Dann", [self.south], ReminderMessage.State.PLANNED),
        )
        self.assertEqual(ReminderMessage.objects.count(), 2)

    def test_a_sent_email_is_not_edited_any_more(self):
        self.two_points()
        self.write("send")
        queued = ReminderMessage.objects.get()
        self.assertRedirects(
            self.client.get(self.edit_url(queued)), self.reminder_url()
        )
        self.assertRedirects(
            self.write(mail=queued, subject="Geändert"), self.reminder_url()
        )
        queued.refresh_from_db()
        self.assertEqual(queued.subject, "Abholung")

    def test_table_lists_drafts_first_then_the_newest_with_their_state(self):
        self.two_points()
        sent = self.make_draft(
            subject="Gesendet",
            state=ReminderMessage.State.SENT,
            send_log=["Müller@example.com"],
            error_log={"Meier@example.com": "Mailbox voll"},
            sent_date=timezone.now() - timedelta(hours=2),
        )
        sent.orders.set(CustomerOrder.objects.all()[:2])
        queued = self.make_draft(subject="Wartet", state=ReminderMessage.State.SENDING)
        queued.orders.set(CustomerOrder.objects.filter(point_of_sale=self.south))
        self.make_draft(subject="Entwurf", points=[self.north, self.south])
        page = self.page()
        self.assertEqual(
            self.mail_rows(page),
            [
                ("Entwurf", "N, Süd", 3, ReminderMessage.State.PLANNED),
                ("Wartet", "Alle", 2, ReminderMessage.State.SENDING),
                ("Gesendet", "Alle", 2, ReminderMessage.State.SENT),
            ],
        )
        self.assertContains(page, "Wird gesendet")
        self.assertContains(page, "Fehler (1)")
        self.assertEqual(
            [str(action.label) for action in page.context["reminder_actions"]],
            ["Neue E-Mail"],
        )

    def test_view_shows_the_email_and_its_recipients(self):
        self.two_points()
        sent = self.make_draft(
            subject="Für {{ last_name }}",
            state=ReminderMessage.State.SENT,
            send_log=["Meier@example.com"],
            error_log={"Schulze@example.com": "Mailbox voll"},
            sent_date=timezone.now(),
        )
        sent.orders.set(CustomerOrder.objects.filter(point_of_sale=self.south))
        response = self.client.get(self.mail_url("mail", pk=sent.pk))
        self.assertTemplateNotUsed(response, "workshop/base.html")
        self.assertContains(response, "Für Meier")
        self.assertContains(response, "Zugestellt an (1):</strong> Meier@example.com")
        self.assertContains(response, "Schulze@example.com (Mailbox voll)")
        draft = self.make_draft(points=[self.north])
        response = self.client.get(self.mail_url("mail", pk=draft.pk))
        self.assertContains(response, "Hallo Müller")
        self.assertContains(response, "Geht an (1):</strong> Müller@example.com")

    def test_a_queued_email_goes_back_to_a_draft_until_it_is_sent(self):
        self.two_points()
        self.write("send", points=[self.north.pk])
        queued = ReminderMessage.objects.get()
        response = self.post(take_back=queued.pk)
        self.assertRedirects(response, self.reminder_url())
        queued.refresh_from_db()
        self.assertEqual(
            (queued.state, list(queued.orders.all())),
            (ReminderMessage.State.PLANNED, []),
        )
        # The command sends nothing taken back.
        self.deliver()
        self.assertEqual(mail.outbox, [])
        # Once the command took it, it stays with the command.
        self.post(send=queued.pk)
        queued.refresh_from_db()
        self.assertTrue(queued.claim_for_sending())
        self.post(take_back=queued.pk)
        queued.refresh_from_db()
        self.assertEqual(queued.state, ReminderMessage.State.SENDING)
        self.assertFalse(queued.claim_for_sending())

    def test_delete_removes_only_drafts(self):
        self.two_points()
        draft = self.make_draft()
        self.write("send")
        queued = ReminderMessage.objects.get(
            state=ReminderMessage.State.PLANNED_SENDING
        )
        self.post(delete=draft.pk)
        self.post(delete=queued.pk)
        self.assertEqual(list(ReminderMessage.objects.all()), [queued])

    def test_duplicate_is_a_new_draft_with_text_and_recipients(self):
        self.two_points()
        self.customer_order(self.production_day, "Ohne")
        self.write("send", subject="Zweimal", points=[self.south.pk, "none"])
        self.deliver()
        sent = ReminderMessage.objects.get(state=ReminderMessage.State.SENT)
        response = self.post(duplicate=sent.pk)
        copy = ReminderMessage.objects.exclude(pk=sent.pk).get()
        self.assertRedirects(response, self.edit_url(copy))
        self.assertEqual(
            (
                copy.state,
                copy.subject,
                copy.body,
                list(copy.points_of_sale.all()),
                copy.without_point_of_sale,
                list(copy.orders.all()),
            ),
            (
                ReminderMessage.State.PLANNED,
                "Zweimal",
                sent.body,
                [self.south],
                True,
                [],
            ),
        )

    def tab_badge(self):
        tabs = self.page().context["day_switch"]["tabs"]
        return [tab.get("badge") for tab in tabs if tab["key"] == "reminder"][0]

    def test_tab_shows_how_far_the_mails_got(self):
        self.two_points()
        self.make_draft()
        self.assertIsNone(self.tab_badge())
        self.write("send", points=[self.north.pk])
        self.assertEqual(self.tab_badge(), "1 / 3")
        self.write("send", points=[self.south.pk])
        self.assertEqual(self.tab_badge(), "✓")

    def preview(self, subject, **data):
        return self.client.post(
            self.mail_url("preview"),
            {"subject": subject, "body": self.body(), **data},
        )

    def test_preview_uses_the_first_order_of_the_chosen_recipients(self):
        response = self.preview("Für {{ last_name }}")
        # Without orders the example customer.
        self.assertContains(response, "Für Musteruser")
        self.assertTemplateNotUsed(response, "workshop/base.html")
        self.two_points()
        self.assertContains(self.preview("Für {{ last_name }}"), "Für Müller")
        response = self.preview(
            "Für {{ last_name }}", recipients="points", points=[self.south.pk]
        )
        self.assertContains(response, "Für Meier")
        self.assertContains(response, "Hallo Meier")

    def test_test_email_goes_to_me_and_saves_nothing(self):
        self.two_points()
        # The placeholders of the order are filled with the first recipient's.
        response = self.write(
            "send_test", subject="Test für {{ point_of_sale }}", points=[self.south.pk]
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(message.to, message.subject) for message in mail.outbox],
            [(["baker@example.com"], "Test für Süd")],
        )
        self.assertFalse(ReminderMessage.objects.exists())

    def test_pickup_email_pages_need_a_staff_user(self):
        self.two_points()
        draft = self.make_draft()
        login = reverse("login")
        # The pages answer a customer with 403, the parts loaded into them
        # send to the login like the other parts of the workshop.
        urls = [
            (self.reminder_url(), 403),
            (self.new_url(), 403),
            (self.edit_url(draft), 403),
            (self.mail_url("mail", pk=draft.pk), 302),
            (self.mail_url("preview"), 302),
        ]
        customer = TenantClient(self.tenant)
        customer.force_login(User.objects.get(username="Müller"))
        for url, customer_status in urls:
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    # Posted as the editor of the draft, which also sends it.
                    data = (
                        {}
                        if method == "get"
                        else {
                            "editor": draft.pk,
                            "send": "",
                            "recipients": "all",
                            "subject": "x",
                            "body": self.body(),
                        }
                    )
                    response = getattr(TenantClient(self.tenant), method)(url, data)
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith(login), response.url)
                    response = getattr(customer, method)(url, data)
                    self.assertEqual(response.status_code, customer_status)
            with self.subTest(url=url, staff=True):
                self.assertEqual(self.client.get(url).status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(
            (draft.state, draft.subject), (ReminderMessage.State.PLANNED, "Entwurf")
        )


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
