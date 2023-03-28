from django.db import models
from django.db.models import F

class ProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(product_template__isnull=True)
    

class ProductHierarchyManager(models.Manager):
    def with_weights(self):
        return self.annotate(
            calculated_weight=F('quantity') * F('child__weight')
        ).order_by('-calculated_weight')

class ProductionDayProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(product_template__isnull=False)