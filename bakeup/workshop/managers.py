from django.db.models import F

from bakeup.core.models import AbstractBaseManager


class ProductManager(AbstractBaseManager):
    def get_queryset(self):
        return super().get_queryset().filter(product_template__isnull=True)

    def templates(self, *args, **kwargs):
        return (
            super().get_queryset(*args, **kwargs).filter(product_template__isnull=False)
        )


class ProductHierarchyManager(AbstractBaseManager):
    def with_weights(self):
        return self.annotate(
            calculated_weight=F("quantity") * F("child__weight")
        ).order_by("-calculated_weight")


class ProductionDayProductManager(AbstractBaseManager):
    def get_queryset(self):
        return super().get_queryset().filter(product_template__isnull=False)
