from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from bakeup.shop.models import CustomerOrderPosition, ProductionDay
from bakeup.workshop.models import ProductionPlan

STATES = {
    "planned": ProductionPlan.State.PLANNED,
    "production": ProductionPlan.State.IN_PRODUCTION,
    "produced": ProductionPlan.State.PRODUCED,
}


class Command(BaseCommand):
    # Runs in the schema of one tenant:
    # manage.py tenant_command create_production_plans_without_recipe --schema=<tenant>
    #
    # The workshop skips products without a recipe, see
    # ProductionDay._create_production_plan, and removes their planned plans
    # again when the production day is saved or started. A plan in production
    # or produced stays, so start the plans of a day with --state production.
    help = "Creates the production plans of the products without a recipe"

    def add_arguments(self, parser):
        parser.add_argument(
            "--day",
            type=date.fromisoformat,
            help="Day of sale (YYYY-MM-DD), default are all days from today on",
        )
        parser.add_argument(
            "--state",
            choices=STATES,
            default="planned",
            help="planned takes the max quantity, the others the ordered quantity",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        state = STATES[options["state"]]
        if options["day"]:
            production_days = ProductionDay.objects.filter(day_of_sale=options["day"])
            if not production_days.exists():
                raise CommandError(f"No production day on {options['day']}")
        else:
            production_days = ProductionDay.objects.filter(
                day_of_sale__gte=timezone.now().date()
            )
        for production_day in production_days.order_by("day_of_sale"):
            day_products = production_day.production_day_products.filter(
                product__parents__isnull=True
            ).select_related("product")
            for day_product in day_products:
                product = day_product.product
                positions = CustomerOrderPosition.objects.filter(
                    Q(product=product) | Q(product__product_template=product),
                    order__production_day=production_day,
                )
                if state == ProductionPlan.State.PLANNED:
                    quantity = day_product.max_quantity or 0
                else:
                    quantity = positions.aggregate(Sum("quantity"))["quantity__sum"]
                # A plan in production or produced is locked and stays as it is.
                plan = production_day._create_production_plan(
                    product, quantity or 0, state, without_recipe=True
                )
                positions.update(production_plan=plan)
                if state != ProductionPlan.State.PLANNED:
                    # The same as starting the plan in the workshop.
                    production_day.update_order_positions_product(plan.product)
                self.stdout.write(
                    f"{production_day.day_of_sale} {product.name}: "
                    f"{plan.quantity:g} {plan.get_state_display()}"
                )
