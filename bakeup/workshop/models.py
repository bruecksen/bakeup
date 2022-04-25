from django.db import models
from django.db.models import Q, F
from django.urls import reverse

from treebeard.mp_tree import MP_Node

from bakeup.core.models import CommonBaseClass



class Category(CommonBaseClass, MP_Node):
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    image = models.FileField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    node_order_by = ['name']

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

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
    name = models.CharField(max_length=255)
    slug = models.SlugField(null=True, blank=True)
    description = models.TextField()
    image = models.FileField(null=True, blank=True)
    categories = models.ManyToManyField(Category, blank=True)
    # data in database normalized in grams
    weight = models.PositiveSmallIntegerField(help_text="weight in grams", blank=True, null=True)
    weight_units = models.CharField(max_length=255, choices=WEIGHT_UNIT_CHOICES, blank=True, null=True)
    # data in database normalized in milliliter
    volume = models.PositiveSmallIntegerField(help_text="weight in grams", blank=True, null=True)
    volume_units = models.CharField(max_length=255, choices=VOLUME_UNIT_CHOICES, blank=True, null=True)
    is_sellable = models.BooleanField(default=False)
    is_buyable = models.BooleanField(default=False)
    is_composable = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("workshop:product-detail", kwargs={"pk": self.pk})
    
    def add_child(self, child):
        child = ProductHierarchy.objects.create(
            parent=self,
            child=child,
            quantity=1
        )
        return child


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
    quantity = models.PositiveSmallIntegerField()

    
    class Meta:
        unique_together = ('parent', 'child')
        constraints = [
            models.CheckConstraint(
                check=~Q(parent=F('child')),
                name='recipe_parent_and_child_cannot_be_equal'
            )
        ]


class ProductionPlan(CommonBaseClass):
    start_date = models.DateTimeField()
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_plans')
    quantity = models.PositiveSmallIntegerField()
    duration = models.PositiveSmallIntegerField()







