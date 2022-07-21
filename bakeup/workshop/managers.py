from django.db import models

class ProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(product_template__isnull=True)


class ProductionDayProductManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(product_template__isnull=False)