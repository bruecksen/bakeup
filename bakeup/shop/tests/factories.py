from datetime import timedelta

from django.utils import timezone
from factory import Sequence, SubFactory, post_generation
from factory.django import DjangoModelFactory

from bakeup.shop.models import (
    CustomerOrder,
    PointOfSale,
    PointOfSalePickupTime,
    ProductionDay,
)


class PointOfSaleFactory(DjangoModelFactory):
    name = Sequence(lambda n: f"Point of sale {n}")

    class Meta:
        model = PointOfSale
        skip_postgeneration_save = True

    @post_generation
    def pickup_times(self, create, extracted, **kwargs):
        # pickup_times=[(4, "16:00", "18:00")] is Friday from 16 to 18.
        for day_of_the_week, from_time, to_time in extracted or []:
            PointOfSalePickupTime.objects.create(
                point_of_sale=self,
                day_of_the_week=day_of_the_week,
                from_time=from_time,
                to_time=to_time,
            )


class ProductionDayFactory(DjangoModelFactory):
    day_of_sale = Sequence(lambda n: timezone.now().date() + timedelta(days=n + 1))

    class Meta:
        model = ProductionDay


class CustomerOrderFactory(DjangoModelFactory):
    production_day = SubFactory(ProductionDayFactory)

    class Meta:
        model = CustomerOrder
