from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import connection, models
from django.db.models import F, Q, Sum
from django.template import Context, Template
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from taggit.managers import TaggableManager
from treebeard.mp_tree import MP_Node, get_result_class

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
    # data in database normalized in milliliter
    is_sellable = models.BooleanField(default=False, verbose_name=_("Is sellable"))
    is_buyable = models.BooleanField(default=False, verbose_name=_("Is buyable"))
    is_composable = models.BooleanField(default=False, verbose_name=_("Is composable"))
    is_recurring = models.BooleanField(default=False, verbose_name=_("Is abo product?"))
    max_recurring_order_qty = models.PositiveSmallIntegerField(
        blank=True, null=True, verbose_name=_("Max abo quantity?")
    )

    tags = TaggableManager(blank=True, ordering=["name"])
    objects = ProductManager()
    production = ProductionDayProductManager()

    class Meta:
        ordering = ("name",)

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
        return child

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
        return Product.calculate_total_weight(self) or self.weight

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
        category = Category.objects.filter(slug="liquids").first()
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
        category = Category.objects.filter(slug="salt").first()
        if not category:
            return None
        total_weight_flour = self.total_weight_flour
        total_salt = Product.calculate_total_weight_by_category(self, category)
        if total_weight_flour and total_salt:
            return round(total_salt / total_weight_flour * 100, 2)

    def get_starter_ratio(self):
        return 10

    def get_pre_ferment_ratio(self):
        category = Category.objects.filter(slug="flour").first()
        category_parent = Category.objects.filter(slug="pre-dough").first()
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
        category = Category.objects.filter(slug="flour").first()
        if not category:
            return None
        return Product.calculate_total_weight_by_category(self, category)

    @property
    def is_normalized(self):
        return round(self.total_weight) == 1000

    def get_wheats(self):
        category = Category.objects.filter(slug="flour").first()
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
        if total_weight and self.weight:
            return round(1 - (self.weight / self.total_weight), 4) * 100

    def normalize(self, fermentation_loss):
        if self.total_weight and self.weight:
            current_fermantation_loss = round(1 - (self.weight / self.total_weight), 4)
            fermentation_loss = fermentation_loss / Decimal(100)
            delta_weight_addon = (1 - Decimal(current_fermantation_loss)) / (
                1 - fermentation_loss
            )
            for child in self.parents.all():
                child.quantity = child.quantity * float(delta_weight_addon)
                child.save(update_fields=["quantity"])


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
                check=~Q(parent=F("child")),
                name="recipe_parent_and_child_cannot_be_equal",
            )
        ]

    @property
    def is_leaf(self):
        return not self.child.parents.exists()

    @property
    def weight(self):
        if self.child.weight:
            return self.child.weight * self.quantity
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
                check=~Q(pk=F("parent_plan")), name="production_plan_not_equal_parent"
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

    def get_state_css_class(self):
        if self.is_planned:
            return "bg-secondary"
        elif self.is_production:
            return "bg-warning"
        elif self.is_produced:
            return "bg-success"
        elif self.is_canceled:
            return "bg-dark"

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
    body = models.TextField(
        help_text=(
            "Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{"
            " email }}, {{ order }}, {{ price_total }}, {{ production_day }}, {{"
            " order_count }}, {{ point_of_sale }}"
        )
    )
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
            return f"{ self.point_of_sale }: { self.subject }"
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

    def replace_message_tags(self, message, order, client, production_day):
        t = Template(message)
        message = t.render(
            Context(
                {
                    "site_name": client.name,
                    "user": order.customer.user.get_full_name(),
                    "first_name": order.customer.user.first_name,
                    "last_name": order.customer.user.last_name,
                    "email": order.customer.user.email,
                    "order": order.get_order_positions_string(),
                    "price_total": (
                        order.price_total and Money(order.price_total, "EUR") or ""
                    ),
                    "production_day": production_day.day_of_sale.strftime("%d.%m.%Y"),
                    "order_count": order.total_quantity,
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

    def send_messages(self):
        user_successfull = []
        emails_error = {}
        orders = self.get_orders()
        client = connection.get_tenant()
        for order in orders:
            try:
                user_email = order.customer.user.email
                user_body = self.replace_message_tags(
                    self.body, order, client, self.production_day
                )
                subject = self.replace_message_tags(
                    self.subject, order, client, self.production_day
                )
                send_mail(
                    subject,
                    user_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [user_email],
                    fail_silently=False,
                )
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
