from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.db.models import (
    F,
    Prefetch,
    ProtectedError,
    Q,
    Sum,
    prefetch_related_objects,
)
from django.template import Context, Template
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from taggit.managers import TaggableManager
from treebeard.mp_tree import MP_Node, get_result_class
from wagtail.fields import RichTextField

from bakeup.core.models import CommonBaseClass
from bakeup.workshop.managers import (
    ProductHierarchyManager,
    ProductionDayProductManager,
    ProductManager,
)
from bakeup.workshop.templatetags.workshop_tags import clever_rounding


class Category(CommonBaseClass, MP_Node):
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    image = models.FileField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    node_order_by = ["name"]

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ("name",)

    def __str__(self):
        return "{} {}".format("-" * (self.depth - 1), self.name)

    def get_descendants(self, include_self=False):
        if include_self:
            return self.__class__.get_tree(self)
        if self.is_leaf():
            return get_result_class(self.__class__).objects.none()
        return self.__class__.get_tree(self).exclude(pk=self.pk)

    def get_product_count(self):
        return Product.objects.filter(
            category__in=self.get_descendants(include_self=True)
        ).count()


WEIGHT_UNIT_CHOICES = [
    ("g", _("Grams")),
    ("kg", _("Kilograms")),
]


def validate_video_file(value):
    # Check that the uploaded file is a video file
    valid_extensions = [".mp4", ".mov", ".avi", ".mkv"]
    if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
        raise ValidationError(
            "Unsupported file extension. Allowed extensions are: .mp4, .mov, .avi, .mkv"
        )


# Item
class Product(CommonBaseClass):
    product_template = models.ForeignKey(
        "workshop.Product", blank=True, null=True, on_delete=models.PROTECT
    )
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    sku = models.CharField(max_length=255, blank=True, null=True, verbose_name="SKU")
    display_name = models.CharField(
        max_length=255, blank=True, null=True, verbose_name=_("display name")
    )
    slug = models.SlugField(null=True, blank=True)
    description = models.TextField(null=True, blank=True, verbose_name=_("Description"))
    image = models.FileField(
        null=True, blank=True, upload_to="product_images", verbose_name=_("Image")
    )
    image_secondary = models.FileField(
        null=True,
        blank=True,
        upload_to="product_images",
        verbose_name=_("Secondary Image"),
    )
    video_file = models.FileField(
        upload_to="videos/", validators=[validate_video_file], blank=True, null=True
    )
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_("Category"),
    )
    # data in database normalized in grams
    weight = models.FloatField(
        help_text=_("weight in grams"), default=1000, verbose_name=_("Weight")
    )
    uom = models.ForeignKey(
        "core.UOM", on_delete=models.SET_NULL, blank=True, null=True
    )
    # data in database normalized in milliliter
    is_sellable = models.BooleanField(default=False, verbose_name=_("Is sellable"))
    is_buyable = models.BooleanField(default=False, verbose_name=_("Is buyable"))
    is_composable = models.BooleanField(default=False, verbose_name=_("Is composable"))
    is_recurring = models.BooleanField(default=False, verbose_name=_("Is abo product?"))
    is_bio_certified = models.BooleanField(
        default=False, verbose_name=_("Is bio certified?")
    )
    max_recurring_order_qty = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name=_("Max abo quantity?")
    )
    max_order_qty = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name=_("Max order quantity?")
    )

    tags = TaggableManager(blank=True, ordering=["name"])
    objects = ProductManager()
    production = ProductionDayProductManager()

    class Meta:
        ordering = ("name",)

    def delete(self, *args, **kwargs):
        try:
            super().delete(*args, **kwargs)
        except ProtectedError:
            self.is_archived = True
            self.save()

    @classmethod
    def delete_product_tree(self, product):
        for child in product.parents.all():
            Product.delete_product_tree(child.child)
        product.delete()

    def __str__(self):
        return self.name

    @classmethod
    def duplicate(cls, product):
        children = list(product.parents.all())
        product_template_id = product.pk
        product.pk = None
        product.product_template_id = product_template_id
        product.save()
        for child in children:
            duplicate_child = Product.duplicate(child.child)
            ProductHierarchy.objects.create(
                parent=product, child=duplicate_child, quantity=child.quantity
            )
        return product

    @property
    def sale_price(self):
        return self.sale_prices.first()

    @property
    def category_name(self):
        return self.category and self.category.name or None

    @property
    def unit(self):
        return "g"

    @property
    def weight_in_base_unit(self):
        return self.uom and self.uom.to_base_unit(self.weight) or self.weight

    def convert_weight(self, target_uom):
        base_weight = self.weight_in_base_unit
        return target_uom.from_base_unit(base_weight)

    @property
    def is_open_for_abo(self):
        if self.is_recurring:
            if self.max_recurring_order_qty:
                if self.available_abo_quantity <= 0:
                    return False
            return True
        return False

    @property
    def abo_sum(self):
        return (
            self.customerordertemplateposition_positions.active().aggregate(
                Sum("quantity")
            )["quantity__sum"]
            or 0
        )

    @property
    def abo_count(self):
        return self.customerordertemplateposition_positions.active().count()

    @property
    def available_abo_quantity(self):
        if self.max_recurring_order_qty:
            return self.max_recurring_order_qty - self.abo_sum

    def get_short_name(self):
        return self.sku or self.name

    def get_display_name(self):
        return self.display_name or self.name

    def get_absolute_url(self):
        return reverse("workshop:product-detail", kwargs={"pk": self.pk})

    def has_child(self, child):
        return ProductHierarchy.objects.filter(parent=self, child=child).exists()

    def add_child(self, child, quantity=1):
        child = ProductHierarchy.objects.create(
            parent=self, child=child, quantity=quantity
        )
        self.clear_recipe_cache()
        return child

    def load_recipe_tree(self):
        prefetch_recipe_trees([self])
        return self

    def clear_recipe_cache(self):
        # The loaded recipe tree and the figures derived from it are stale once
        # quantities or rows changed.
        self.__dict__.pop("_total_weight_flour", None)
        getattr(self, "_prefetched_objects_cache", {}).pop("parents", None)

    def get_recipe_category(self, slug):
        categories = self.__dict__.setdefault("_recipe_categories", {})
        if slug not in categories:
            categories[slug] = Category.objects.filter(slug=slug).first()
        return categories[slug]

    def get_children_by_weight(self):
        # Same order as ProductHierarchy.objects.with_weights(), but uses a
        # loaded recipe tree.
        return sorted(
            self.parents.all(),
            key=lambda child: child.quantity * child.child.weight,
            reverse=True,
        )

    def get_full_ingredient_list(self):
        ingredients = defaultdict(int)

        def generate_ingredient_list(product, quantity):
            for child in product.parents.all():
                if child.is_leaf:
                    product_weight = quantity * child.weight
                    ingredients[child.child] = ingredients[child.child] + product_weight
                else:
                    generate_ingredient_list(child.child, quantity * child.quantity)

        generate_ingredient_list(self, 1)
        ingredients = sorted(ingredients.items(), key=lambda kv: kv[1], reverse=True)
        return ingredients

    def get_ingredient_list(self):
        ingredients = []
        for child in self.parents.all():
            ingredients.append(
                {
                    "product": child.child,
                    "quantity": child.quantity,
                }
            )
        return ingredients

    @property
    def total_weight(self):
        return Product.calculate_total_weight(self) or self.weight_in_base_unit

    @classmethod
    def calculate_total_weight(cls, product, quantity=1):
        weight = 0
        for child in product.parents.all():
            product_weight = quantity * child.weight
            weight += product_weight
        return weight

    @classmethod
    def calculate_total_weight_by_category(cls, product, category, quantity=1):
        weight = 0
        for child in product.parents.all():
            if child.child.category and (
                child.child.category.is_descendant_of(category)
                or child.child.category == category
            ):
                product_weight = quantity * child.weight
                weight += product_weight
            else:
                weight += Product.calculate_total_weight_by_category(
                    child.child, category, quantity * child.quantity
                )
        return weight

    @classmethod
    def calculate_total_weight_by_category_and_parent(
        cls, product, category, quantity=1, parent_category=None, do_count=False
    ):
        weight = 0
        # Flag that we hit the parent category
        if not parent_category or product.category == parent_category:
            do_count = True

        for child in product.parents.all():
            if (
                child.child.category.is_descendant_of(category)
                or child.child.category == category
            ):
                if do_count is True:
                    product_weight = quantity * child.weight
                    weight += product_weight
            else:
                weight += Product.calculate_total_weight_by_category_and_parent(
                    child.child,
                    category,
                    quantity * child.quantity,
                    parent_category,
                    do_count,
                )
        # and turn if of again
        if not parent_category or product.category == parent_category:
            do_count = False

        return weight

    @classmethod
    def calculate_total_weight_by_ingredient(cls, product, ingredient, quantity=1):
        weight = 0
        for child in product.parents.all():
            if child.child == ingredient:
                product_weight = quantity * child.weight
                # print("{}({}) {}".format(child.child, child.child.category.name, product_weight))
                weight += product_weight
            else:
                weight += Product.calculate_total_weight_by_ingredient(
                    child.child, ingredient, quantity * child.quantity
                )
        return weight

    def get_dough_yield(self):
        # Netto-Teigausbeute 100 x (Wasser + Mehl) / Mehl
        category = self.get_recipe_category("liquids")
        if not category:
            return None
        total_weight_water = Product.calculate_total_weight_by_category(self, category)
        total_weight_flour = self.total_weight_flour
        if total_weight_flour and total_weight_water:
            dough_yield = (
                100 * (total_weight_water + total_weight_flour) / total_weight_flour
            )
            return round(dough_yield)

    def get_salt_ratio(self):
        category = self.get_recipe_category("salt")
        if not category:
            return None
        total_weight_flour = self.total_weight_flour
        total_salt = Product.calculate_total_weight_by_category(self, category)
        if total_weight_flour and total_salt:
            return round(total_salt / total_weight_flour * 100, 2)

    def get_starter_ratio(self):
        return 10

    def get_pre_ferment_ratio(self):
        category = self.get_recipe_category("flour")
        category_parent = self.get_recipe_category("pre-dough")
        if not category or not category_parent:
            return None
        total_weight = self.total_weight_flour
        total_pre_dough = Product.calculate_total_weight_by_category_and_parent(
            self, category, 1, category_parent
        )
        # raise Exception(total_pre_dough)
        if total_weight and total_pre_dough:
            return round(total_pre_dough / total_weight * 100, 2)

    @property
    def total_weight_flour(self):
        if "_total_weight_flour" not in self.__dict__:
            category = self.get_recipe_category("flour")
            self._total_weight_flour = category and (
                Product.calculate_total_weight_by_category(self, category)
            )
        return self._total_weight_flour

    @property
    def is_normalized(self):
        return round(self.total_weight) == 1000

    def get_wheats(self):
        category = self.get_recipe_category("flour")
        if not category:
            return None
        wheats = ""
        total_weight_flour = self.total_weight_flour
        for category in Category.objects.filter(
            path__startswith="{}{}".format(category.path, "0")
        ):
            weight = Product.calculate_total_weight_by_category(self, category)
            if weight:
                if wheats:
                    wheats += "\n"
                wheats += "{} ({}%)".format(
                    category.name, clever_rounding(weight / total_weight_flour * 100)
                )
        return wheats

    def get_fermentation_loss(self):
        total_weight = self.total_weight
        if total_weight and self.weight_in_base_unit:
            return round(1 - (self.weight_in_base_unit / self.total_weight), 4) * 100

    def normalize(self, fermentation_loss):
        if self.total_weight and self.weight_in_base_unit:
            current_fermantation_loss = round(
                1 - (self.weight_in_base_unit / self.total_weight), 4
            )
            fermentation_loss = fermentation_loss / Decimal(100)
            delta_weight_addon = (1 - Decimal(current_fermantation_loss)) / (
                1 - fermentation_loss
            )
            for child in self.parents.all():
                child.quantity = child.quantity * float(delta_weight_addon)
                child.save(update_fields=["quantity"])
            self.clear_recipe_cache()

    def adjust_ratio_to_flour(self, category_slug, ratio, keep_total_weight=True):
        # Only the ingredients of the category on this level are changed, sub
        # levels keep their composition. With keep_total_weight this level is
        # rescaled afterwards so the total weight stays the same, otherwise the
        # flour stays and the total weight follows.
        category = self.get_recipe_category(category_slug)
        total_weight_flour = self.total_weight_flour
        if not category or not total_weight_flour:
            return False
        total_weight_category = Product.calculate_total_weight_by_category(
            self, category
        )
        children = list(self.parents.all())
        ingredients = [
            child
            for child in children
            if child.child.category
            and child.child.weight_in_base_unit
            and (
                child.child.category == category
                or child.child.category.is_descendant_of(category)
            )
        ]
        weight_direct = sum(child.weight for child in ingredients)
        if not weight_direct:
            return False
        target_weight = total_weight_flour * ratio / 100
        new_weight_direct = weight_direct + target_weight - total_weight_category
        if new_weight_direct <= 0:
            return False
        factor = new_weight_direct / weight_direct
        total_weight = sum(
            child.weight for child in children if child.child.weight_in_base_unit
        )
        scale = 1
        if keep_total_weight:
            scale = total_weight / (total_weight - weight_direct + new_weight_direct)
        for child in children:
            if child in ingredients:
                child.quantity = child.quantity * factor * scale
            else:
                child.quantity = child.quantity * scale
            child.save(update_fields=["quantity"])
        self.clear_recipe_cache()
        return True

    def adjust_dough_yield(self, dough_yield, keep_total_weight=True):
        return self.adjust_ratio_to_flour(
            "liquids", dough_yield - 100, keep_total_weight
        )

    def adjust_salt_ratio(self, salt_ratio, keep_total_weight=True):
        return self.adjust_ratio_to_flour("salt", float(salt_ratio), keep_total_weight)

    def get_flour_children(self):
        flour = self.get_recipe_category("flour")
        if not flour:
            return []
        return [
            child
            for child in self.parents.all()
            if child.child.weight_in_base_unit
            and child.child.category
            and (
                child.child.category == flour
                or child.child.category.is_descendant_of(flour)
            )
        ]

    def adjust_child_ratio(
        self, hierarchy, ratio, keep_total_weight=True, balancing=None
    ):
        # Sets one row to ratio percent of the total flour, r = ratio / 100.
        # The row may contain flour itself (a flour or a pre dough).
        # With keep_total_weight the flour may change: with the flour of the
        # other rows F and the flour share f of the row the new row weight W
        # solves W = r * (F + f * W), afterwards this level is rescaled so the
        # total weight stays the same, which keeps all ratios.
        # Otherwise the total flour stays: W = r * F and the flour the row adds
        # or removes is compensated by the balancing flour row, or by all other
        # flours on this level when there is none or the row is the balancing
        # flour itself.
        # Use the row of the loaded recipe tree, the passed one may be loaded
        # on its own.
        hierarchy = next(
            (child for child in self.parents.all() if child.pk == hierarchy.pk),
            hierarchy,
        )
        total_weight_flour = self.total_weight_flour
        weight = hierarchy.child.weight_in_base_unit and hierarchy.weight
        if not total_weight_flour or not weight or ratio <= 0:
            return False
        flours = self.get_flour_children()
        if any(child.pk == hierarchy.pk for child in flours):
            flour_in_row = weight
        else:
            flour = self.get_recipe_category("flour")
            flour_in_row = Product.calculate_total_weight_by_category(
                hierarchy.child, flour, hierarchy.quantity
            )
        ratio = float(ratio) / 100
        children = list(self.parents.all())
        factors = {}
        if keep_total_weight:
            other_flour = total_weight_flour - flour_in_row
            denominator = 1 - ratio * flour_in_row / weight
            if other_flour <= 0 or denominator <= 0:
                return False
            new_weight = ratio * other_flour / denominator
        else:
            new_weight = ratio * total_weight_flour
            delta_flour = flour_in_row / weight * (new_weight - weight)
            if abs(delta_flour) > 1e-9:
                compensating = [child for child in flours if child.pk != hierarchy.pk]
                if balancing and balancing.pk != hierarchy.pk:
                    compensating = [
                        child for child in compensating if child.pk == balancing.pk
                    ]
                weight_flours = sum(child.weight for child in compensating)
                if not weight_flours or weight_flours - delta_flour <= 0:
                    return False
                for child in compensating:
                    factors[child.pk] = (weight_flours - delta_flour) / weight_flours
        factors[hierarchy.pk] = new_weight / weight
        scale = 1
        if keep_total_weight:
            total_weight = sum(
                child.weight for child in children if child.child.weight_in_base_unit
            )
            new_total_weight = sum(
                child.weight * factors.get(child.pk, 1)
                for child in children
                if child.child.weight_in_base_unit
            )
            scale = total_weight / new_total_weight
        for child in children:
            child.quantity = child.quantity * factors.get(child.pk, 1) * scale
            child.save(update_fields=["quantity"])
        self.clear_recipe_cache()
        return True

    def adjust_total_weight(self, total_weight):
        children = list(self.parents.all())
        current_total_weight = sum(
            child.weight for child in children if child.child.weight_in_base_unit
        )
        if not current_total_weight or total_weight <= 0:
            return False
        scale = float(total_weight) / current_total_weight
        for child in children:
            child.quantity = child.quantity * scale
            child.save(update_fields=["quantity"])
        self.clear_recipe_cache()
        return True

    def adjust_pre_ferment_ratio(self, pre_ferment, keep_total_weight=True):
        # The pre doughs on this level are scaled. The flour (per flour type),
        # liquids and salt they add or remove are compensated on this level, so
        # flour composition, dough yield and salt ratio stay. With
        # keep_total_weight this level is rescaled afterwards so the total
        # weight stays the same.
        flour = self.get_recipe_category("flour")
        liquids = self.get_recipe_category("liquids")
        pre_dough = self.get_recipe_category("pre-dough")
        salt = self.get_recipe_category("salt")
        total_weight_flour = self.total_weight_flour
        if not flour or not liquids or not pre_dough or not total_weight_flour:
            return False
        children = list(self.parents.all())

        def direct_children(category, exact=False):
            return [
                child
                for child in children
                if child.child.category
                and child.child.weight_in_base_unit
                and (
                    child.child.category == category
                    or (not exact and child.child.category.is_descendant_of(category))
                )
            ]

        pre_doughs = direct_children(pre_dough)

        def weight_in_pre_doughs(category):
            return sum(
                Product.calculate_total_weight_by_category(
                    child.child, category, child.quantity
                )
                for child in pre_doughs
            )

        flour_in_pre_doughs = weight_in_pre_doughs(flour)
        if not flour_in_pre_doughs:
            return False
        total_pre_ferment = Product.calculate_total_weight_by_category_and_parent(
            self, flour, 1, pre_dough
        )
        target_pre_ferment = total_weight_flour * float(pre_ferment) / 100
        factor = (
            target_pre_ferment - (total_pre_ferment - flour_in_pre_doughs)
        ) / flour_in_pre_doughs
        if factor <= 0:
            return False
        factors = {child.pk: factor for child in pre_doughs}

        flour_types = [(category, False) for category in flour.get_children()]
        flour_types.append((flour, True))
        flour_in_flour_types = 0
        compensations = []
        for category, exact in flour_types:
            if exact:
                weight = flour_in_pre_doughs - flour_in_flour_types
            else:
                weight = weight_in_pre_doughs(category)
                flour_in_flour_types += weight
            compensations.append((direct_children(category, exact), weight))
        compensations.append((direct_children(liquids), weight_in_pre_doughs(liquids)))
        if salt:
            compensations.append((direct_children(salt), weight_in_pre_doughs(salt)))
        for compensated_children, weight_in_pre_dough in compensations:
            delta_weight = (factor - 1) * weight_in_pre_dough
            if abs(delta_weight) < 1e-9:
                continue
            weight = sum(child.weight for child in compensated_children)
            if not weight or weight - delta_weight <= 0:
                return False
            for child in compensated_children:
                factors[child.pk] = (weight - delta_weight) / weight

        total_weight = sum(
            child.weight for child in children if child.child.weight_in_base_unit
        )
        new_total_weight = sum(
            child.weight * factors.get(child.pk, 1)
            for child in children
            if child.child.weight_in_base_unit
        )
        scale = total_weight / new_total_weight if keep_total_weight else 1
        for child in children:
            child.quantity = child.quantity * factors.get(child.pk, 1) * scale
            child.save(update_fields=["quantity"])
        self.clear_recipe_cache()
        return True


class ProductPrice(CommonBaseClass):
    product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="sale_prices",
    )
    price = MoneyField(
        max_digits=14, decimal_places=2, default_currency="EUR", verbose_name=_("Price")
    )


# Assembly
class Instruction(CommonBaseClass):
    product = models.OneToOneField(
        "workshop.Product", on_delete=models.CASCADE, related_name="instructions"
    )
    instruction = models.TextField(blank=True, null=True, verbose_name=_("Instruction"))
    duration = models.PositiveSmallIntegerField(
        help_text="duration in seconds", blank=True, null=True
    )


"""
Add this in verison 0.2

# Charge
class ProductRevision(CommonBaseClass):
    product = models.ForeignKey('workshop.Product', on_delete=models.CASCADE, related_name='revisions')
    timestamp = models.DateTimeField(auto_now_add=True)
    from_date = models.DateTimeField()
    to_date = models.DateTimeField()

    class Meta:
        unique_together = ('product', 'timestamp')
        ordering = ('-timestamp',)
 """


# Hierarchy, Recipe
# Warning: Changes on product level are not presisted
# NOTE maybe add later revision to reflect changes on product level
class ProductHierarchy(CommonBaseClass):
    parent = models.ForeignKey(
        "workshop.Product", on_delete=models.CASCADE, related_name="parents"
    )
    child = models.ForeignKey(
        "workshop.Product", on_delete=models.CASCADE, related_name="childs"
    )
    quantity = models.FloatField()

    objects = ProductHierarchyManager()

    class Meta:
        ordering = ("pk",)
        unique_together = ("parent", "child")
        constraints = [
            models.CheckConstraint(
                condition=~Q(parent=F("child")),
                name="recipe_parent_and_child_cannot_be_equal",
            )
        ]

    @property
    def is_leaf(self):
        return not self.child.parents.exists()

    @property
    def weight(self):
        if self.child.weight_in_base_unit:
            return self.child.weight_in_base_unit * self.quantity
        else:
            return "-"


class ProductMapping(CommonBaseClass):
    source_product = models.ForeignKey(
        "workshop.Product", on_delete=models.CASCADE, related_name="source_product"
    )
    target_product = models.ForeignKey(
        "workshop.Product", on_delete=models.CASCADE, related_name="target_product"
    )
    production_day = models.ForeignKey(
        "shop.ProductionDay",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="product_mapping",
    )
    matched_count = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        ordering = ("production_day",)

    @classmethod
    def latest_product_mappings(cls, count):
        latest_mappings = []
        for production_day in (
            ProductMapping.objects.all()
            .values("production_day", "production_day__day_of_sale")
            .distinct()[:count]
        ):
            product_mappings = []
            for product_mapping in ProductMapping.objects.filter(
                production_day=production_day.get("production_day")
            ):
                product_mappings.append(product_mapping)
            latest_mappings.append(
                {
                    "production_day": production_day.get("production_day__day_of_sale"),
                    "product_mappings": product_mappings,
                }
            )
        return latest_mappings


class ProductionPlan(CommonBaseClass):
    class State(models.IntegerChoices):
        PLANNED = 0
        IN_PRODUCTION = 1
        PRODUCED = 2
        CANCELED = 3

    state = models.IntegerField(choices=State.choices, default=State.PLANNED)
    production_day = models.ForeignKey(
        "shop.ProductionDay",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="production_plans",
    )
    parent_plan = models.ForeignKey(
        "workshop.ProductionPlan",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    start_date = models.DateField(null=True, blank=True)
    product = models.ForeignKey(
        "workshop.Product",
        on_delete=models.CASCADE,
        related_name="production_plans",
        blank=True,
    )
    quantity = models.FloatField()
    duration = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("-production_day", "product__name")
        constraints = [
            models.CheckConstraint(
                condition=~Q(pk=F("parent_plan")),
                name="production_plan_not_equal_parent",
            )
        ]

    def __str__(self):
        return "ProductionPlan {} {} {}".format(
            self.production_day, self.product, self.state
        )

    @property
    def is_locked(self):
        return self.state > 0

    @property
    def is_planned(self):
        return self.state == self.State.PLANNED

    @property
    def is_production(self):
        return self.state == self.State.IN_PRODUCTION

    @property
    def is_produced(self):
        return self.state == self.State.PRODUCED

    @property
    def is_canceled(self):
        return self.state == self.State.CANCELED

    def delete(self):
        Product.delete_product_tree(self.product)
        super().delete()

    @classmethod
    def state_display_value(self, value):
        if value == 0:
            return "geplant"
        elif value == 1:
            return "in produktion"
        elif value == 2:
            return "produziert"
        elif value == 3:
            return "abgebrochen"

    def get_state_display_value(self):
        return ProductionPlan.state_display_value(self.state)

    @classmethod
    def state_css_class(self, value):
        if value == self.State.PLANNED:
            return "bg-secondary"
        elif value == self.State.IN_PRODUCTION:
            return "bg-warning"
        elif value == self.State.PRODUCED:
            return "bg-success"
        elif value == self.State.CANCELED:
            return "bg-dark"

    def get_state_css_class(self):
        return ProductionPlan.state_css_class(self.state)

    def get_next_state(self):
        if self.is_planned:
            return self.State.IN_PRODUCTION
        elif self.is_production:
            return self.State.PRODUCED
        return None

    def set_state(self, state):
        self.state = state
        self.save(update_fields=["state"])

    def set_next_state(self):
        self.set_state(self.get_next_state())

    def set_production(self):
        self.set_state(self.State.IN_PRODUCTION)

    @classmethod
    def create_all_child_plans(cls, parent, children, quantity_parent):
        for child in children:
            if not child.is_leaf:
                # print("Productionplan: {}".format(child.child))
                obj, created = ProductionPlan.objects.update_or_create(
                    parent_plan=parent,
                    production_day=parent.production_day,
                    start_date=parent.start_date,
                    product=child.child,
                    defaults={"quantity": quantity_parent * child.quantity},
                )
                ProductionPlan.create_all_child_plans(
                    obj, child.child.parents.all(), quantity_parent * child.quantity
                )


class ReminderMessage(CommonBaseClass):
    class State(models.IntegerChoices):
        PLANNED = 0
        SENT = 1
        PLANNED_SENDING = 2
        SENDING = 3

    state = models.IntegerField(choices=State.choices, default=State.PLANNED)
    subject = models.TextField()
    body = RichTextField(
        editor="email",
        help_text=(
            "Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{"
            " email }}, {{ order }}, {{ order_link }}, {{ order_link_text }}, {{"
            " price_total }}, {{ production_day }}, {{ order_count }}, {{"
            " point_of_sale }}"
        ),
    )
    # body = models.TextField(
    #     help_text=(
    #         "Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{"
    #         " email }}, {{ order }}, {{ price_total }}, {{ production_day }}, {{"
    #         " order_count }}, {{ point_of_sale }}"
    #     )
    # )
    point_of_sale = models.ForeignKey(
        "shop.PointOfSale", blank=True, null=True, on_delete=models.CASCADE
    )
    production_day = models.ForeignKey("shop.ProductionDay", on_delete=models.CASCADE)
    send_log = models.JSONField(default=dict)
    error_log = models.JSONField(default=dict)
    sent_date = models.DateTimeField(blank=True, null=True)
    users = models.ManyToManyField("users.User", blank=True)

    class Meta:
        ordering = ["-sent_date"]

    def __str__(self):
        if self.point_of_sale:
            return f"{self.point_of_sale}: {self.subject}"
        else:
            return self.subject

    @property
    def is_planned(self):
        return self.state == ReminderMessage.State.PLANNED

    @property
    def is_sent(self):
        return self.state == ReminderMessage.State.SENT

    @property
    def is_sending(self):
        return self.state == ReminderMessage.State.SENDING

    @property
    def is_planned_sending(self):
        return self.state == ReminderMessage.State.PLANNED_SENDING

    def get_orders(self):
        if self.point_of_sale:
            return self.production_day.customer_orders.filter(
                point_of_sale=self.point_of_sale
            )
        else:
            return self.production_day.customer_orders.all()

    def replace_message_tags(self, message, order, user, client, production_day):
        t = Template(message)
        order_link = "{}{}#bestellung-{}".format(
            client.default_full_url,
            reverse_lazy("shop:order-list"),
            self.pk,
        )
        message = t.render(
            Context(
                {
                    "site_name": client.name,
                    "user": user.get_full_name(),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "order": SafeString(order.get_order_positions_string(html=True)),
                    "price_total": (
                        order.price_total and Money(order.price_total, "EUR") or ""
                    ),
                    "production_day": production_day.day_of_sale.strftime("%d.%m.%Y"),
                    "order_count": order.total_quantity,
                    "order_link_text": SafeString(
                        "<a href='{}'>{}</a>".format(order_link, "jetzt ändern")
                    ),
                    "order_link": order_link,
                    "point_of_sale": order.point_of_sale,
                }
            )
        )
        return message

    def set_state_to_sending(self):
        self.state = ReminderMessage.State.SENDING
        self.save(
            update_fields=[
                "state",
            ]
        )

    def set_state_to_planned_sending(self):
        self.state = ReminderMessage.State.PLANNED_SENDING
        self.save(
            update_fields=[
                "state",
            ]
        )

    def send_email(self, user, order, client):
        from bakeup.newsletter.backend import send_mass_html_mail
        from bakeup.pages.models import BrandSettings, EmailSettings

        messages = []
        email = user.email
        user_body = self.replace_message_tags(
            self.body, order, user, client, self.production_day
        )
        subject = self.replace_message_tags(
            self.subject, order, user, client, self.production_day
        )
        context = {
            "body": user_body,
            "page": self,
            "brand_settings": BrandSettings.load(
                client.default_site
            ),  # BrandSettings.load(request)
            "email_settings": EmailSettings.load(
                client.default_site
            ),  # EmailSettings.load(request)
            "contact": None,
            "absolute_url": client.default_full_url,
        }
        html = render_to_string(
            template_name="emails/system_email.html",
            context=context,
        )
        message_data = {
            "subject": subject,
            "from_email": settings.DEFAULT_FROM_EMAIL,
            "to": [email],
            "reply_to": [settings.DEFAULT_FROM_EMAIL],
            "html_body": html,
        }
        messages.append(message_data)
        send_mass_html_mail(messages)

    def send_messages(self):
        user_successfull = []
        emails_error = {}
        orders = self.get_orders()
        client = connection.get_tenant()
        for order in orders:
            try:
                user_email = order.customer.user.email
                self.send_email(order.customer.user, order, client)
                user_successfull.append(order.customer.user)
            except Exception as e:
                emails_error[user_email] = str(e)

        self.state = ReminderMessage.State.SENT
        self.send_log = [user.email for user in user_successfull]
        self.users.add(*user_successfull)
        self.error_log = emails_error
        self.sent_date = timezone.now()
        self.save(
            update_fields=[
                "state",
                "send_log",
                "error_log",
                "sent_date",
                "send_log",
                "error_log",
            ]
        )


def prefetch_recipe_trees(products):
    # Loads the recipes of the products with all their sub recipes, one query
    # per recipe level. Afterwards parents.all(), child, category and uom of
    # every row in the trees don't hit the database. A product that shows up
    # again, e.g. water in the pre dough and the main dough, shares the rows
    # loaded first.
    loaded = {}
    level = [product for product in products if product is not None]
    while level:
        to_load = [product for product in level if product.pk not in loaded]
        prefetch_related_objects(
            to_load,
            Prefetch(
                "parents",
                queryset=ProductHierarchy.objects.select_related(
                    "child__category", "child__uom__base_unit"
                ),
            ),
        )
        for product in to_load:
            loaded.setdefault(product.pk, product)
        for product in level:
            if product.pk in loaded and loaded[product.pk] is not product:
                cache = product.__dict__.setdefault("_prefetched_objects_cache", {})
                cache["parents"] = loaded[product.pk]._prefetched_objects_cache[
                    "parents"
                ]
        level = [child.child for product in to_load for child in product.parents.all()]
