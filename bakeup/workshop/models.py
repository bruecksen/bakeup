from django.db import models
from django.db.models import Q, F

from bakeup.core.models import CommonBaseClass, TenantModel



class Category(TenantModel, CommonBaseClass):
    parent = models.ForeignKey('workshop.Category', blank=True, null=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    image = models.FileField()
    description = models.TextField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~Q(parent=F('id')),
                name='category_id_and_parent_not_equal'
            )
        ]

WEIGHT_UNIT_CHOICES = [
    ('g', 'Grams'),
    ('kg', 'Kilograms'),
]

VOLUME_UNIT_CHOICES = [
    ('ml', 'Milliliter'),
    ('l', 'Liter'),
]

# Item
class Product(TenantModel, CommonBaseClass):
    name = models.CharField(max_length=255)
    slug = models.SlugField()
    description = models.TextField()
    image = models.FileField()
    categories = models.ManyToManyField(Category)
    # data in database normalized in grams
    weight = models.PositiveSmallIntegerField(help_text="weight in grams", blank=True, null=True)
    weight_units = models.CharField(max_length=255, choices=WEIGHT_UNIT_CHOICES, blank=True, null=True)
    # data in database normalized in milliliter
    volume = models.PositiveSmallIntegerField(help_text="weight in grams", blank=True, null=True)
    volume_units = models.CharField(max_length=255, choices=VOLUME_UNIT_CHOICES, blank=True, null=True)
    is_sellable = models.BooleanField(default=False)
    is_buyable = models.BooleanField(default=False)
    is_composable = models.BooleanField(default=False)


# Assembly
class Instruction(TenantModel, CommonBaseClass):
    product = models.ForeignKey('workshop.Product', on_delete=models.CASCADE, related_name='instructions')
    instruction = models.TextField()
    duration = models.PositiveSmallIntegerField(help_text="duration in seconds")


# Charge
class ProductRevision(TenantModel, CommonBaseClass):
    product = models.ForeignKey('workshop.Product', on_delete=models.CASCADE, related_name='revisions')
    timestamp = models.DateTimeField(auto_now_add=True)
    from_date = models.DateTimeField()
    to_date = models.DateTimeField()

    class Meta:
        unique_together = ('product', 'timestamp')
        ordering = ('-timestamp',)


# Hierarchy, Recipe
# Warning: Changes on product level are not presisted
# NOTE maybe add later revision to reflect changes on product level
class ProductHierarchy(TenantModel, CommonBaseClass):
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


class ProductionPlan(TenantModel, CommonBaseClass):
    start_date = models.DateTimeField()
    product = models.ForeignKey('workshop.ProductRevision', on_delete=models.PROTECT, related_name='production_plans')
    quantity = models.PositiveSmallIntegerField()
    duration = models.PositiveSmallIntegerField()







