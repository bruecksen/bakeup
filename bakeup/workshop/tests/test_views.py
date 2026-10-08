from datetime import timedelta

from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation
from django_tenants.test.client import TenantClient

from bakeup.contrib.models import Note
from bakeup.shop.models import (
    CustomerOrder,
    CustomerOrderPosition,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.users.models import User
from bakeup.workshop.models import (
    Instruction,
    Product,
    ProductHierarchy,
    ProductionPlan,
)
from bakeup.workshop.templatetags.workshop_tags import clever_unit
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
        self.assertContains(response, f'id="step-{plan.pk}"')
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
        self.client.post(
            reverse(
                "workshop:production-plan-ingredients-toggle-all",
                kwargs={"pk": starter.pk},
            )
        )
        self.assertEqual(current(), ["Sourdough"])

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
