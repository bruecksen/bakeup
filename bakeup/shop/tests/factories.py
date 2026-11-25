from datetime import timedelta

from django.utils import timezone
from factory import LazyFunction, Sequence, SubFactory, post_generation
from factory.django import DjangoModelFactory

from bakeup.shop.models import (
    CustomerOrder,
    CustomerOrderPosition,
    CustomerOrderTemplate,
    CustomerOrderTemplatePosition,
    CustomerOrderTemplateSkip,
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


class CustomerOrderPositionFactory(DjangoModelFactory):
    order = SubFactory(CustomerOrderFactory)
    quantity = 1

    class Meta:
        model = CustomerOrderPosition


class CustomerOrderTemplateFactory(DjangoModelFactory):
    # An abo that is already running.
    start_date = LazyFunction(lambda: timezone.now() - timedelta(days=1))

    class Meta:
        model = CustomerOrderTemplate


class CustomerOrderTemplatePositionFactory(DjangoModelFactory):
    order_template = SubFactory(CustomerOrderTemplateFactory)
    quantity = 1

    class Meta:
        model = CustomerOrderTemplatePosition


class CustomerOrderTemplateSkipFactory(DjangoModelFactory):
    production_day = SubFactory(ProductionDayFactory)

    class Meta:
        model = CustomerOrderTemplateSkip
