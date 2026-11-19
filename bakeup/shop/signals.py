from django.db.models import ProtectedError
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from bakeup.shop.models import (
    CustomerOrder,
    CustomerOrderPosition,
    ProductionDay,
    ProductionDayProduct,
)
from bakeup.workshop.models import ProductionPlan


@receiver(post_save, sender=CustomerOrderPosition)
def update_production_plan(sender, instance, **kwargs):
    production_plan = ProductionPlan.objects.filter(
        production_day=instance.order.production_day,
        product__product_template=instance.product,
    ).first()
    if not instance.production_plan and production_plan:
        instance.production_plan = production_plan
        instance.save(update_fields=["production_plan"])


@receiver(pre_delete, sender=CustomerOrder)
def protect_customer_orders(sender, instance, using, **kwargs):
    if hasattr(instance, "force_delete") and instance.force_delete:
        return
    if instance.positions.filter(production_plan__state__gt=0):
        positions = instance.positions.filter(production_plan__state__gt=0).distinct()
        production_plans = [p.production_plan for p in positions]
        raise ProtectedError(
            "Only orders with unstarted production plans can be deleted.",
            production_plans,
        )


@receiver(pre_delete, sender=ProductionDayProduct)
def protect_production_day_product(sender, instance, using, **kwargs):
    if CustomerOrderPosition.objects.filter(
        order__production_day=instance.production_day, product=instance.product
    ).exists():
        raise ProtectedError("Only products without orders can be deleted.", instance)


@receiver(post_delete, sender=ProductionDayProduct)
def delete_stale_production_plans(sender, instance, origin=None, **kwargs):
    # The plan hangs on the day product with SET_NULL, so nothing else removes
    # it when the day product goes (edit form, delete view, Django admin).
    # origin is the object or queryset delete() was called on. When that is the
    # production day, its plans cascade anyway and the day may be gone already.
    if isinstance(origin, ProductionDay) or getattr(origin, "model", None) is (
        ProductionDay
    ):
        return
    instance.production_day.delete_stale_production_plans()
