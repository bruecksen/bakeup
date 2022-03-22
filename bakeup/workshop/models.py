from django.db import models
from django.db.models import Q, F

from bakeup.core.models import TenantModelMixin


class CommonBaseClass(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Category(TenantModelMixin, CommonBaseClass):
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

# TODO hierachy


WEIGHT_UNIT_CHOICES = [
    ('g', 'Grams'),
    ('kg', 'Kilograms'),
]

VOLUME_UNIT_CHOICES = [
    ('ml', 'Milliliter'),
    ('l', 'Liter'),
]

# Item
class Product(TenantModelMixin, CommonBaseClass):
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


# Assembly
class Instruction(TenantModelMixin, CommonBaseClass):
    product = models.ForeignKey('workshop.Product', on_delete=models.CASCADE)
    instruction = models.TextField()
    duration = models.PositiveSmallIntegerField(help_text="duration in seconds")


class ProductRevision(TenantModelMixin, CommonBaseClass):
    product = models.ForeignKey('workshop.Product', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    from_date = models.DateTimeField()
    to_date = models.DateTimeField()

    class Meta:
        unique_together = ('product', 'timestamp')
        ordering = ('-timestamp')


# Hierachy, Recipe
class ProductRevisionHierachy(TenantModelMixin, CommonBaseClass):
    parent = models.ForeignKey('workshop.ProductRevision', on_delete=models.CASCADE)
    child = models.ForeignKey('workshop.ProductRevision', on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField()
    
    class Meta:
        unique_together = ('parent', 'child')
        ordering = ('-timestamp')
        constraints = [
            models.CheckConstraint(
                check=~Q(parent=F('child')),
                name='recipe_parent_and_child_cannot_be_equal'
            )
        ]

