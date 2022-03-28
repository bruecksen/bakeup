from django.db import models

from recurrence.fields import RecurrenceField

from bakeup.core.models import CommonBaseClass

DAYS_OF_WEEK = (
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
)


class ProductionDayTemplate(CommonBaseClass):
    day_of_the_week = models.CharField(max_length=1, choices=DAYS_OF_WEEK)
    calendar_week = models.PositiveSmallIntegerField(null=True, blank=True)
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_day_templates')
    quantity = models.PositiveSmallIntegerField()


class ProductionDay(CommonBaseClass):
    day_of_sale = models.DateField()
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_days')
    max_quantity = models.PositiveSmallIntegerField()
    is_open_for_orders = models.BooleanField(default=True)


class PointOfSale(CommonBaseClass):
    name = models.CharField(max_length=255)
    address = models.OneToOneField('core.Address', on_delete=models.PROTECT)

    def __str__(self):
        return self.name


# TODO how to handle public holidays, exceptional closing days, etc.
class PointOfSaleOpeningHour(CommonBaseClass):
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.PROTECT, related_name='opening_hours')
    day_of_the_week = models.IntegerField(choices=DAYS_OF_WEEK)
    from_time = models.TimeField()
    to_time = models.TimeField()

    class Meta:
        ordering = ('day_of_the_week',)

    def __str__(self):
        return self.point_of_sale.name


class Customer(CommonBaseClass):
    user = models.OneToOneField('users.User', on_delete=models.PROTECT)
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.PROTECT, blank=True, null=True)

    def __str__(self):
        return "{} {}".format(self.user, self.point_of_sale)

# Abo
# TODO install django-recurrence
class CustomerOrderTemplate(CommonBaseClass):
    customer = models.ForeignKey('shop.Customer', on_delete=models.PROTECT, related_name='order_templates')
    from_date = models.DateField()
    to_date = models.DateField()
    day_of_the_week = models.CharField(max_length=1, choices=DAYS_OF_WEEK, blank=True, null=True)
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='order_templates')
    quantity = models.PositiveSmallIntegerField()
    recurrences = RecurrenceField()


class CustomerOrder(CommonBaseClass):
    order_nr = models.CharField(max_length=255)
    day_of_sale = models.DateField()
    customer = models.OneToOneField('shop.Customer', on_delete=models.PROTECT, blank=True, null=True, related_name='orders')
    point_of_sale = models.OneToOneField('shop.PointOfSale', on_delete=models.PROTECT, blank=True, null=True)
    address = models.TextField()


class CustomerOrderPosition(CommonBaseClass):
    order = models.ForeignKey('shop.CustomerOrder', on_delete=models.PROTECT, related_name='positions')
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='order_positions')
    quantity = models.PositiveSmallIntegerField()

    


    




# class ProductionDay