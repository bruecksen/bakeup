from django.db.models import Sum
from django_tenants.utils import tenant_context

from bakeup.core.models import Client
from bakeup.shop.models import CustomerOrder, CustomerOrderPosition, ProductionDay

order_count, customer_count, production_days, baked_goods = 0, 0, 0, 0
for client in Client.objects.all():
    with tenant_context(client):
        # active customers
        customer_count += (
            CustomerOrder.objects.filter(created__gte="2024-01-01")
            .values_list("customer")
            .distinct()
            .count()
        )
        order_count += CustomerOrder.objects.filter(created__gte="2024-01-01").count()
        production_days += ProductionDay.objects.filter(
            day_of_sale__gte="2024-01-01"
        ).count()
        baked_goods += (
            CustomerOrderPosition.objects.filter(
                order__production_day__day_of_sale__gte="2024-01-01"
            ).aggregate(Sum("quantity"))["quantity__sum"]
            or 0
        )

print(f"Customer count: {customer_count}")
print(f"Order count: {order_count}")
print(f"Production days: {production_days}")
print(f"Baked goods: {baked_goods}")
