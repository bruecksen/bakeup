import collections

from django.urls import reverse
from datetime import datetime
from django.db import models
from django.db.models import Sum
from django.db.models import Q, F
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

class ProductionDayQuerySet(models.QuerySet):
    def upcoming(self):
        today = datetime.now().date()
        return self.filter(day_of_sale__gte=today).order_by('day_of_sale')


class ProductionDay(CommonBaseClass):
    day_of_sale = models.DateField(unique=True)
    description = models.TextField(blank=True, null=True)

    objects = ProductionDayQuerySet.as_manager()

    class Meta:
        ordering = ('-day_of_sale',)

    def __str__(self):
        return "{}".format(self.day_of_sale.strftime("%d.%m.%Y"))

    def get_absolute_url(self):
        return reverse('workshop:production-day-detail', kwargs={'pk': self.pk })

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

    def update_production_plan(self, filter_product, create_max_quantity):
        ProductionPlan.objects.get(product__product_template=filter_product, production_day=self).delete()
        self.create_production_plans(filter_product, create_max_quantity)

    @property
    def total_ordered_quantity(self):
        return CustomerOrderPosition.objects.filter(order__production_day=self).aggregate(Sum('quantity'))['quantity__sum']
    
    @property
    def total_published_ordered_quantity(self):
        return CustomerOrderPosition.objects.filter(order__production_day=self, product__in=self.production_day_products.filter(is_published=True).values_list('product', flat=True)).aggregate(Sum('quantity'))['quantity__sum']

    def create_production_plans(self, filter_product=None, create_max_quantity=False):
        if filter_product:
            positions = CustomerOrderPosition.objects.filter(order__production_day=self, product=filter_product)
        else:
            positions = CustomerOrderPosition.objects.filter(order__production_day=self)
        product_quantities = positions.values('product').order_by('product').annotate(total_quantity=Sum('quantity'))
        if not product_quantities and create_max_quantity:
            # fallback to max product quantities of production day
            if filter_product:
                product_quantities = self.production_day_products.filter(product=filter_product).values('product', total_quantity=F('max_quantity'))
            else:
                product_quantities = self.production_day_products.values('product', total_quantity=F('max_quantity'))
        for product_quantity in product_quantities:
            product_template = Product.objects.get(pk=product_quantity.get('product'))
            if product_quantity.get('total_quantity') == 0:
                continue
            if ProductionPlan.objects.filter(production_day=self, parent_plan=None, product__product_template=product_template).exists():
                if not ProductionPlan.objects.get(production_day=self, parent_plan=None, product__product_template=product_template).is_locked:
                    self.update_production_plan(product_template, create_max_quantity)
                continue
            product = Product.duplicate(product_template)
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

    def get_ingredient_summary_list(self):
        ingredients = {}
        for production_plan in self.production_plans.filter(parent_plan__isnull=True):
            for child in ProductionPlan.objects.filter(
                Q(parent_plan=production_plan) | 
                Q(parent_plan__parent_plan=production_plan) | 
                Q(parent_plan__parent_plan__parent_plan=production_plan) |
                Q(parent_plan__parent_plan__parent_plan__parent_plan=production_plan)):
                print(child.product.name)
                for ingredient in child.product.get_ingredient_list():
                    product = ingredient['product']
                    quantity = ingredient['quantity']
                    # ingredient.product.weight|multiply:plan.quantity|multiply:ingredient.quantity|floatformat:0
                    category = product.category.get_parent() or product.category
                    category = ingredients.setdefault(category, {})
                    product_quantity = category.setdefault(product.product_template, 0)
                    category_sum = category.setdefault('sum', 0)
                    product_quantity = product_quantity + (product.weight * child.quantity * quantity)
                    if product.name == 'Salz':
                        print(product.name, product.weight, child.quantity, quantity, product_quantity)
                    category[product.product_template] = product_quantity
                    category_sum = category_sum + (product.weight * child.quantity * quantity)
                    category['sum'] = category_sum
        return collections.OrderedDict(sorted(ingredients.items(), key=lambda t: t[0].path))


class ProductionDayProduct(CommonBaseClass):
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.CASCADE, related_name='production_day_products')
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_days', limit_choices_to={'is_sellable': True})
    max_quantity = models.PositiveSmallIntegerField()
    production_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, blank=True, null=True)
    is_published = models.BooleanField(default=False, verbose_name="Published?")
    
    class Meta:
        ordering = ('production_day', 'product')
        unique_together = ['production_day', 'product']

    @property
    def is_sold_out(self):
        return self.calculate_max_quantity() <= 0

    @property
    def is_locked(self):
        return self.production_plan and self.production_plan.is_locked
    
    def get_order_form(self, customer=None):
        from bakeup.shop.forms import CustomerOrderBatchForm
        quantity = 0
        if customer:
            existing_order = CustomerOrderPosition.objects.filter(product=self.product, order__customer=customer, order__production_day=self.production_day)
            if existing_order:
                quantity = existing_order.first().quantity
        form = CustomerOrderBatchForm(
            initial={'product': self.product.pk, 'quantity': quantity}, 
            prefix=f'production_day_{self.product.pk}', 
            production_day_product=self,
            customer=customer
        )
        return form

    def get_order_quantity(self):
        orders = CustomerOrderPosition.objects.filter(
            product=self.product, 
            order__production_day=self.production_day
        )
        return orders.aggregate(quantity_sum=Sum('quantity'))['quantity_sum'] or 0

    def calculate_max_quantity(self, exclude_customer=None):
        orders = CustomerOrderPosition.objects.filter(
            product=self.product, 
            order__production_day=self.production_day
        )
        if exclude_customer:
            orders = orders.exclude(order__customer=exclude_customer)
        ordered_quantity = orders.aggregate(quantity_sum=Sum('quantity'))['quantity_sum'] or 0
        return max(self.max_quantity - ordered_quantity, 0)


class PointOfSale(CommonBaseClass):
    name = models.CharField(max_length=255)
    address = models.OneToOneField('contrib.Address', on_delete=models.PROTECT)
    is_primary = models.BooleanField(default=False)

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
    user = models.OneToOneField('users.User', on_delete=models.CASCADE)
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ('user__email', )

    def __str__(self):
        return "{}".format(self.user)
    

# Abo
# TODO install django-recurrence
class CustomerOrderTemplate(CommonBaseClass):
    customer = models.ForeignKey('shop.Customer', on_delete=models.PROTECT, related_name='order_templates')
    from_date = models.DateField(blank=True, null=True)
    to_date = models.DateField(blank=True, null=True)
    day_of_the_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK, blank=True, null=True)
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='order_templates')
    quantity = models.PositiveSmallIntegerField()
    recurrences = RecurrenceField(blank=True, null=True)


class CustomerOrder(CommonBaseClass):
    # order_nr = models.CharField(max_length=255)
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.PROTECT, related_name='customer_orders')
    customer = models.ForeignKey('shop.Customer', on_delete=models.PROTECT, blank=True, null=True, related_name='orders')
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.SET_NULL, blank=True, null=True, related_name='customer_orders')
    address = models.TextField()

    class Meta:
        unique_together = ['production_day', 'customer']
        ordering = ['-production_day', '-created']

    def __str__(self):
        return "{} {}".format(self.production_day, self.customer)
    
    def get_order_positions_string(self):
        return "\n".join(["{}x {}".format(position.quantity, position.product) for position in self.positions.all()])

    @property
    def is_planned(self):
        return self.positions.filter(production_plan__isnull=False).exists()

    @property
    def order_nr(self):
        """
        Return an order number for a given basket
        """
        return 100000 + self.pk


    @classmethod
    def create_or_update_customer_order_position(cls, production_day, customer, product, quantity):
        # TODO order_nr, address, should point of sale really be saved in order?
        customer_order, created_order = CustomerOrder.objects.update_or_create(
            production_day=production_day,
            customer=customer,
            defaults={
                'point_of_sale': customer.point_of_sale,
            }
        )
        position, created = CustomerOrderPosition.objects.get_or_create(
            order=customer_order,
            product=product,
            defaults={'quantity': quantity}
        )
        if not created:
            position.quantity = (position.quantity or 0) + quantity
            position.save(update_fields=['quantity'])
            
        return created_order


    @classmethod
    def create_or_update_customer_order(cls, production_day, customer, products):
        # TODO order_nr, address, should point of sale really be saved in order?
        customer_order, created_order = CustomerOrder.objects.update_or_create(
            production_day=production_day,
            customer=customer,
            defaults={
                'point_of_sale': customer.point_of_sale,
            }
        )
        for product, quantity in products.items():
            if quantity > 0:
                position, created = CustomerOrderPosition.objects.get_or_create(
                    order=customer_order,
                    product=product,
                    defaults={
                        'quantity': quantity
                    }
                )
                if not created:
                    position.quantity = (position.quantity or 0) + quantity
                    position.save(update_fields=['quantity'])
            
        if CustomerOrderPosition.objects.filter(order=customer_order).count() == 0:
            customer_order.delete()
            return None
        return created_order


class CustomerOrderPositionQuerySet(models.QuerySet):
    def produced(self):
        return self.filter(production_plan__state=ProductionPlan.State.PRODUCED)



class CustomerOrderPosition(CommonBaseClass):
    order = models.ForeignKey('shop.CustomerOrder', on_delete=models.CASCADE, related_name='positions')
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='order_positions')
    production_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    quantity = models.PositiveSmallIntegerField()

    objects = CustomerOrderPositionQuerySet.as_manager()

    class Meta:
        ordering = ['product']

    

    


    




# class ProductionDay