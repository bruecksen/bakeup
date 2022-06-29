from decimal import Decimal
from re import T
from django.db import models
from django.db.models import Q, F
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator

from treebeard.mp_tree import MP_Node

from bakeup.core.models import CommonBaseClass
from bakeup.workshop.managers import ProductManager, ProductionDayProductManager



class Category(CommonBaseClass, MP_Node):
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    image = models.FileField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    node_order_by = ['name']

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return '{} {}'.format('-' * (self.depth - 1), self.name)

    def get_product_count(self):
        return self.product_set.count()


WEIGHT_UNIT_CHOICES = [
    ('g', 'Grams'),
    ('kg', 'Kilograms'),
]

VOLUME_UNIT_CHOICES = [
    ('ml', 'Milliliter'),
    ('l', 'Liter'),
]

# Item
class Product(CommonBaseClass):
    product_template = models.ForeignKey('workshop.Product', blank=True, null=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    slug = models.SlugField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    image = models.FileField(null=True, blank=True, upload_to='product_images')
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.PROTECT)
    # data in database normalized in grams
    weight = models.PositiveSmallIntegerField(help_text="weight in grams", blank=True, null=True)
    weight_units = models.CharField(max_length=255, choices=WEIGHT_UNIT_CHOICES, blank=True, null=True)
    # data in database normalized in milliliter
    volume = models.PositiveSmallIntegerField(help_text="weight in grams", blank=True, null=True)
    volume_units = models.CharField(max_length=255, choices=VOLUME_UNIT_CHOICES, blank=True, null=True)
    is_sellable = models.BooleanField(default=False)
    is_buyable = models.BooleanField(default=False)
    is_composable = models.BooleanField(default=False)


    objects = ProductManager()
    production = ProductionDayProductManager()

    class Meta:
        ordering = ('name',)

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
                parent=product,
                child=duplicate_child,
                quantity=child.quantity
            )
        return product


    def get_absolute_url(self):
        return reverse("workshop:product-detail", kwargs={"pk": self.pk})
    
    def add_child(self, child):
        child = ProductHierarchy.objects.create(
            parent=self,
            child=child,
            quantity=1
        )
        return child

    def get_physical_representation(self):
        if self.weight:
            return "{} {}".format(self.weight, self.weight_units)
        elif self.volume:
            return "{} {}".format(self.volume, self.volume_units)
        else:
            return ''

    def get_weight(self):
        if self.weight_units == "kg":
            return self.weight / 1000
        else:
            return self.weight

    
    def get_ingredient_list(self):
        ingredients = []
        for child in self.parents.all():
            ingredients.append({
                'product': child.child,
                'quantity': child.quantity,
            })
        return ingredients

    @property
    def total_weight(self):
        return Product.calculate_total_weight(self) or self.weight

    @classmethod
    def calculate_total_weight(cls, product, quantity=1):
        weight = 0
        for child in product.parents.all():
            if child.is_leaf:
                product_weight = quantity * child.weight
                weight += product_weight
            else:
                weight += Product.calculate_total_weight(child.child, quantity * child.quantity)
        return weight
    
    @classmethod
    def calculate_total_weight_by_category(cls, product, category, quantity=1):
        weight = 0
        for child in product.parents.all():
            if child.child.category.is_descendant_of(category) or child.child.category == category:
                product_weight = quantity * child.weight
                # print("{}({}) {}".format(child.child, child.child.category.name, product_weight))
                weight += product_weight
            else:
                weight += Product.calculate_total_weight_by_category(child.child, category, quantity * child.quantity)
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
                weight += Product.calculate_total_weight_by_ingredient(child.child, ingredient, quantity * child.quantity)
        return weight

    def get_dough_yield(self):
        # Netto-Teigausbeute 100 x (Wasser + Mehl) / Mehl
        total_weight_water = Product.calculate_total_weight_by_category(self, Category.objects.get(slug='liquids'))
        total_weight_flour = Product.calculate_total_weight_by_category(self, Category.objects.get(slug='flour'))
        if total_weight_flour and total_weight_water:
            dough_yield = 100 * (total_weight_water + total_weight_flour) / total_weight_flour
            return round(dough_yield)

    def get_fermentation_loss(self):
        total_weight = Product.calculate_total_weight(self)
        if total_weight and self.weight:
            return round(100 - (self.weight / total_weight * 100), 2)
    
    def get_salt_ratio(self):
        total_weight_flour = Product.calculate_total_weight_by_category(self, Category.objects.get(slug='flour'))
        total_salt = Product.calculate_total_weight_by_category(self, Category.objects.get(slug='salt'))
        if total_weight_flour and total_salt:
            return round(total_salt / total_weight_flour * 100, 2)
    
    def get_starter_ratio(self):
        return 10
    
    def get_pre_ferment_ratio(self):
        total_weight = Product.calculate_total_weight(self)
        total_pre_dough = Product.calculate_total_weight_by_category(self, Category.objects.get(slug='pre-dough'))
        if total_weight and total_pre_dough:
            return round(total_pre_dough / total_weight * 100, 2)

    @property
    def is_normalized(self):
        return round(self.total_weight) == 1000

    def normalize(self):
        ratio = 1000 / self.total_weight
        for child in self.parents.all():
            if child.is_leaf:
                child.quantity = child.quantity * ratio
                child.save(update_fields=['quantity'])
        self.weight = 1000
        self.save(update_fields=['weight'])
        
        



# Assembly
class Instruction(CommonBaseClass):
    product = models.OneToOneField('workshop.Product', on_delete=models.CASCADE, related_name='instructions')
    instruction = models.TextField()
    duration = models.PositiveSmallIntegerField(help_text="duration in seconds")

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
    parent = models.ForeignKey('workshop.Product', on_delete=models.CASCADE, related_name='parents')
    child = models.ForeignKey('workshop.Product', on_delete=models.CASCADE, related_name='childs')
    quantity = models.FloatField()
    
    class Meta:
        ordering = ('pk',)
        unique_together = ('parent', 'child')
        constraints = [
            models.CheckConstraint(
                check=~Q(parent=F('child')),
                name='recipe_parent_and_child_cannot_be_equal'
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
            return '-'

    @property
    def weight_unit(self):
        if self.child.weight_units:
            return self.child.weight_units
        else:
            return ''
    

class ProductionPlan(CommonBaseClass):
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.SET_NULL, null=True, blank=True, related_name='production_plans')
    parent_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    start_date = models.DateField(null=True, blank=True)
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_plans')
    quantity = models.FloatField()
    duration = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ('pk',)
        constraints = [
            models.CheckConstraint(
                check=~Q(pk=F('parent_plan')),
                name='production_plan_not_equal_parent'
            )
        ]

    @classmethod
    def create_all_child_plans(cls, parent, children, quantity_parent):
        for child in children:
            if not child.is_leaf:
                print("Productionplan: {}".format(child.child))
                obj, created = ProductionPlan.objects.update_or_create(
                    parent_plan=parent,
                    production_day=parent.production_day,
                    start_date=parent.start_date,
                    product=child.child,
                    defaults={'quantity': quantity_parent * child.quantity}
                )
                ProductionPlan.create_all_child_plans(obj, child.child.parents.all(), quantity_parent * child.quantity)








