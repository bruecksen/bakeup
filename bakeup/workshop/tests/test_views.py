import json
from datetime import timedelta
from urllib.parse import quote

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

    def test_product_without_recipe(self):
        # A bakery without recipes still plans, starts and locks its products.
        card = self.cards()[self.cake]
        self.assertFalse(card["has_recipe"])
        self.assertEqual(card["steps"], [])
        self.assertEqual(card["day_product"], self.day_products[self.cake.pk])
        self.assertEqual(
            ProductionDayProduct.objects.get(
                pk=self.day_products[self.cake.pk].pk
            ).production_plan,
            self.root(self.cake),
        )

    def test_order_of_product_without_recipe_is_locked_on_start(self):
        order = CustomerOrder.objects.create(
            production_day=self.production_day, address=""
        )
        CustomerOrderPosition.objects.create(
            order=order,
            product=self.cake,
            quantity=1,
            production_plan=self.root(self.cake),
        )
        self.assertFalse(order.is_locked)
        self.root(self.cake).set_production()
        self.assertTrue(order.is_locked)

    def test_summary(self):
        response = self.client.get(self.day_url())
        summary = response.context["summary"]
        self.assertEqual(summary["products"], 2)
        self.assertEqual(summary["pieces"], 20)
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
                f"{self.day_url()}#production-plan-{self.root().pk}",
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
        self.start()
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
        self.start()
        primary, menu = primary_and_menu()
        self.assertEqual(primary, [finish])
        self.assertNotIn(finish, menu)

    def test_delete_is_disabled_with_orders(self):
        self.add_order()
        response = self.detail()
        delete = [a for a in response.context["day_actions"] if a.danger][0]
        self.assertTrue(delete.disabled)
        self.assertNotContains(response, f'href="{delete.url}"')

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
        self.assertRedirects(response, self.detail_url())
        self.assertTrue(order.positions.get().is_picked_up)


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
