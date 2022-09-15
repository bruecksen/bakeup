from email.policy import default
from django.db import models
from django.db.models import Sum
from django.utils import formats

from recurrence.fields import RecurrenceField

from bakeup.core.models import CommonBaseClass
from bakeup.workshop.models import Product, ProductionPlan

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
    day_of_the_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK)
    calendar_week = models.PositiveSmallIntegerField(null=True, blank=True)
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_day_templates', limit_choices_to={'is_sellable': True})
    quantity = models.PositiveSmallIntegerField()


class ProductionDay(CommonBaseClass):
    day_of_sale = models.DateField(unique=True)

    class Meta:
        ordering = ('-day_of_sale',)

    def __str__(self):
        return "{}".format(self.day_of_sale.strftime("%d.%m.%Y"))

    def has_products_open_for_order(self):
        return self.production_day_products.filter(production_plan__isnull=True).exists()

    @property
    def calendar_week(self):
        return self.day_of_sale.isocalendar()[1]
    
    @property
    def year(self):
        return self.day_of_sale.year

    @property
    def is_locked(self):
        return self.customer_orders.exists()

    def create_production_plans(self, filter_product=None):
        if filter_product:
            positions = CustomerOrderPosition.objects.filter(order__production_day=self, product=filter_product)
        else:
            positions = CustomerOrderPosition.objects.filter(order__production_day=self)
        product_quantities = positions.values('product').order_by('product').annotate(total_quantity=Sum('quantity'))
        for product_quantity in product_quantities:
            if product_quantity.get('total_quantity') == 0:
                continue
            product = Product.duplicate(Product.objects.get(pk=product_quantity.get('product')))
            obj = ProductionPlan.objects.create(
                parent_plan=None,
                production_day=self,
                product=product,
                quantity=product_quantity.get('total_quantity'),
                start_date=self.day_of_sale,
            )
            ProductionPlan.create_all_child_plans(obj, obj.product.parents.all(), quantity_parent=product_quantity.get('total_quantity'))
            positions.filter(product_id=product_quantity.get('product')).update(production_plan=obj)
            production_day_product = ProductionDayProduct.objects.get(product_id=product_quantity.get('product'), production_day=self)
            production_day_product.production_plan = obj
            # production_day_product.product = product
            production_day_product.save()


class ProductionDayProduct(CommonBaseClass):
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.CASCADE, related_name='production_day_products')
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_days', limit_choices_to={'is_sellable': True})
    max_quantity = models.PositiveSmallIntegerField()
    production_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, blank=True, null=True)
    
    class Meta:
        ordering = ('production_day',)
        unique_together = ['production_day', 'product']

    
    def get_order_form(self, customer):
        from bakeup.shop.forms import CustomerOrderForm
        quantity = 0
        existing_order = CustomerOrderPosition.objects.filter(product=self.product, order__customer=customer, order__production_day=self.production_day)
        if existing_order:
            quantity = existing_order.first().quantity
        form = CustomerOrderForm(
            initial={'product': self.product.pk, 'quantity': quantity}, 
            prefix=f'production_day_{self.product.pk}', 
            production_day_product=self,
            customer=customer
        )
        return form

    def calculate_max_quantity(self, exclude_customer=None):
        orders = CustomerOrderPosition.objects.filter(
            product=self.product, 
            order__production_day=self.production_day
        )
        if exclude_customer:
            orders = orders.exclude(order__customer=exclude_customer)
        ordered_quantity = orders.aggregate(quantity_sum=Sum('quantity'))['quantity_sum'] or 0
        return self.max_quantity - ordered_quantity


class PointOfSale(CommonBaseClass):
    name = models.CharField(max_length=255)
    address = models.OneToOneField('contrib.Address', on_delete=models.PROTECT)

    def __str__(self):
        return self.name


# TODO how to handle public holidays, exceptional closing days, etc.
class PointOfSaleOpeningHour(CommonBaseClass):
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.PROTECT, related_name='opening_hours')
    day_of_the_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK)
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
    day_of_the_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK, blank=True, null=True)
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='order_templates')
    quantity = models.PositiveSmallIntegerField()
    recurrences = RecurrenceField()


class CustomerOrder(CommonBaseClass):
    # order_nr = models.CharField(max_length=255)
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.PROTECT, related_name='customer_orders')
    customer = models.ForeignKey('shop.Customer', on_delete=models.PROTECT, blank=True, null=True, related_name='orders')
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.PROTECT, blank=True, null=True)
    address = models.TextField()

    class Meta:
        unique_together = ['production_day', 'customer']

    def __str__(self):
        return "{} {}".format(self.production_day, self.customer)

    @property
    def order_nr(self):
        """
        Return an order number for a given basket
        """
        return 100000 + self.pk


    @classmethod
    def create_customer_order(cls, production_day, customer, products):
        # TODO order_nr, address, should point of sale really be saved in order?
        customer_order, created = CustomerOrder.objects.get_or_create(
            production_day=production_day,
            customer=customer,
            defaults={
                'point_of_sale': customer.point_of_sale,
                'address': "address",
            }
        )
        for product, quantity in products.items():
            position, created = CustomerOrderPosition.objects.update_or_create(
                order=customer_order,
                product=product,
                defaults={
                    'quantity': quantity
                }
            )



class CustomerOrderPosition(CommonBaseClass):
    order = models.ForeignKey('shop.CustomerOrder', on_delete=models.CASCADE, related_name='positions')
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='order_positions')
    production_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    quantity = models.PositiveSmallIntegerField()

    

    


    




# class ProductionDay