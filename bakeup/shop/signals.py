from django.db.models.signals import post_save
from django.dispatch import receiver
from bakeup.shop.models import CustomerOrderPosition
from bakeup.workshop.models import ProductionPlan


@receiver(post_save, sender=CustomerOrderPosition)
def update_production_plan(sender, instance, **kwargs):
    production_plan = ProductionPlan.objects.filter(
        production_day=instance.order.production_day,
        product__product_template=instance.product
    )
    if not instance.production_plan and production_plan.exists():
        instance.production_plan = production_plan.first()
        instance.save(update_fields=['production_plan'])
