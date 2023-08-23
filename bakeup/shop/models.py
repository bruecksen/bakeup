import logging 
import collections

from django.urls import reverse_lazy
from django.core.mail import send_mail
from django.contrib import messages
from django.utils.translation import gettext as _
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.db import models
from django.db.models import Sum
from django.db.models import Q, F, Exists
from django.db.models import OuterRef, Subquery
from django.utils import formats
from django import forms
from django.template import Template, Context
from django.conf import settings

from djmoney.models.fields import MoneyField
from recurrence.fields import RecurrenceField

from bakeup.core.models import CommonBaseClass
from bakeup.workshop.models import Product, ProductionPlan
# from bakeup.pages.models import EmailSettings

logger = logging.getLogger(__name__)

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
    def published(self):
        return self.filter(production_day_products__is_published=True).distinct()

    def upcoming(self):
        today = timezone.now().date()
        return self.filter(day_of_sale__gte=today).order_by('day_of_sale')


class ProductionDay(CommonBaseClass):
    day_of_sale = models.DateField(unique=True)
    description = models.TextField(blank=True, null=True)

    objects = ProductionDayQuerySet.as_manager()

    class Meta:
        ordering = ('-day_of_sale',)

    def __str__(self):
        return "{}".format(self.day_of_sale.strftime("%d.%m.%Y"))

    def get_production_day_production_plan_url(self):
        return reverse('workshop:production-plan-production-day', kwargs={'pk': self.pk })

    def get_absolute_url(self):
        return reverse('workshop:production-day-detail', kwargs={'pk': self.pk })

    def has_products_open_for_order(self):
        return self.production_day_products.filter(production_plan__isnull=True).exists()

    def has_products_with_price(self):
        return self.production_day_products.filter(product__sale_prices__isnull=False).exists()
    
    def get_random_product_image(self):
        product = self.production_day_products.published().exclude(
            Q(product__image='')|
            Q(product__image=None)).order_by('?').first()
        if product:
            return product.product.image
        
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
        ProductionPlan.objects.filter(product__product_template=filter_product, production_day=self).delete()
        return self.create_production_plans(filter_product, create_max_quantity)

    @property
    def total_ordered_quantity(self):
        return CustomerOrderPosition.objects.filter(order__production_day=self).aggregate(Sum('quantity'))['quantity__sum']
    
    @property
    def total_published_ordered_quantity(self):
        return CustomerOrderPosition.objects.filter(order__production_day=self, product__in=self.production_day_products.filter(is_published=True).values_list('product', flat=True)).aggregate(Sum('quantity'))['quantity__sum']

    def create_production_plans(self, filter_product=None, create_max_quantity=False):
        if filter_product:
            positions = CustomerOrderPosition.objects.filter(order__production_day=self, product=filter_product, product__product_template__isnull=True)
        else:
            positions = CustomerOrderPosition.objects.filter(order__production_day=self, product__product_template__isnull=True)
        product_quantities = positions.values('product', 'product__product_template').order_by('product').annotate(total_quantity=Sum('quantity'))
        if not product_quantities and create_max_quantity:
            # fallback to max product quantities of production day
            if filter_product:
                product_quantities = self.production_day_products.filter(product=filter_product).values('product', total_quantity=F('max_quantity'))
            else:
                product_quantities = self.production_day_products.values('product', total_quantity=F('max_quantity'))
        # raise Exception(product_quantities)
        for product_quantity in product_quantities:
            product_template = Product.objects.get(pk=product_quantity.get('product'))
            if product_quantity.get('total_quantity') == 0:
                continue
            if ProductionPlan.objects.filter(production_day=self, parent_plan=None, product__product_template=product_template).exists():
                print('plan exists: {}'.format(product_template))
                if not ProductionPlan.objects.get(production_day=self, parent_plan=None, product__product_template=product_template).is_locked:
                    self.update_production_plan(product_template, create_max_quantity)
                continue
            print('plan create: {}'.format(product_template))
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
            return obj

    def create_template_orders(self):
        with transaction.atomic():
            for product in self.production_day_products.published():
                if not CustomerOrderPosition.objects.filter(order__production_day=self, product=product.product).exists():
                    for order_template_position in CustomerOrderTemplatePosition.objects.active().filter(product=product.product):
                        order_template_position.create_order(self)

    def get_ingredient_summary_list(self):
        ingredients = {}
        for production_plan in self.production_plans.filter(parent_plan__isnull=True):
            for child in ProductionPlan.objects.filter(
                Q(parent_plan=production_plan) | 
                Q(parent_plan__parent_plan=production_plan) | 
                Q(parent_plan__parent_plan__parent_plan=production_plan) |
                Q(parent_plan__parent_plan__parent_plan__parent_plan=production_plan)):
                # print(child.product.name)
                for ingredient in child.product.get_ingredient_list():
                    product = ingredient['product']
                    quantity = ingredient['quantity']
                    # ingredient.product.weight|multiply:plan.quantity|multiply:ingredient.quantity|floatformat:0
                    category = product.category.get_parent() or product.category
                    category = ingredients.setdefault(category, {})
                    product_quantity = category.setdefault(product.product_template, 0)
                    category_sum = category.setdefault('sum', 0)
                    product_quantity = product_quantity + (product.weight * child.quantity * quantity)
                    # if product.name == 'Salz':
                        # print(product.name, product.weight, child.quantity, quantity, product_quantity)
                    category[product.product_template] = product_quantity
                    category_sum = category_sum + (product.weight * child.quantity * quantity)
                    category['sum'] = category_sum
        return collections.OrderedDict(sorted(ingredients.items(), key=lambda t: t[0].path))

    def update_order_positions_product(self, production_plan_product):

        positions = CustomerOrderPosition.objects.filter(
            order__production_day=self, 
            product=production_plan_product.product_template
        )
        positions.update(product=production_plan_product)

class ProductionDayProductQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)
    
    def upcoming(self):
        today = timezone.now().date()
        return self.filter(production_day__day_of_sale__gte=today).order_by('production_day__day_of_sale')
    
    def with_pictures(self):
        return self.exclude(
            Q(product__image='')|
            Q(product__image=None))


class ProductionDayProduct(CommonBaseClass):
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.CASCADE, related_name='production_day_products')
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_days', limit_choices_to={'is_sellable': True})
    max_quantity = models.PositiveSmallIntegerField(blank=False, null=False)
    production_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, blank=True, null=True)
    is_published = models.BooleanField(default=False, verbose_name="Published?")
    
    objects = ProductionDayProductQuerySet.as_manager()

    class Meta:
        ordering = ('production_day', 'product')
        unique_together = ['production_day', 'product']

    def __str__(self):
        return "{}: {}".format(self.production_day, self.product)

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
    short_name = models.CharField(max_length=255, blank=True, null=True)
    address = models.OneToOneField('contrib.Address', on_delete=models.PROTECT, blank=True, null=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    
    def get_short_name(self):
        return self.short_name or self.name
    
    def get_customer_count(self):
        return self.customers.count()
    

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
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.SET_NULL, blank=True, null=True, related_name='customers')
    street = models.CharField(max_length=100, blank=True, null=True)
    street_number = models.CharField(max_length=10, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    telephone_number = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ('user__email', )

    def __str__(self):
        return "{}".format(self.user)
    
    @property
    def total_ordered_positions(self):
        return CustomerOrderPosition.objects.filter(order__customer=self).count()
    
    @property
    def address_line(self):
        if not self.street and not self.street_number:
            return ''
        return f"{self.street or ''} {self.street_number or ''}"


class CustomerOrder(CommonBaseClass):
    # order_nr = models.CharField(max_length=255)
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.PROTECT, related_name='customer_orders')
    customer = models.ForeignKey('shop.Customer', on_delete=models.PROTECT, blank=True, null=True, related_name='orders')
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.SET_NULL, blank=True, null=True, related_name='customer_orders')
    address = models.TextField()

    class Meta:
        unique_together = ['production_day', 'customer']
        ordering = ['production_day', '-created']

    def __str__(self):
        return "{} {}".format(self.production_day, self.customer)
    
    def get_order_positions_string(self):
        return "\n".join(["{}x {}".format(position.quantity, position.product.get_display_name()) for position in self.positions.all()])
    
    @property
    def price_total(self):
        return self.positions.aggregate(price_total=Sum('price_total'))['price_total']

    @property
    def total_quantity(self):
        return self.positions.aggregate(total_quantity=Sum('quantity'))['total_quantity']

    @property
    def is_picked_up(self):
        return not self.positions.filter(is_picked_up=False).exists()

    @property
    def is_planned(self):
        return self.positions.filter(production_plan__isnull=False).exists()
    
    @property
    def is_locked(self):
        return not self.positions.filter(Q(production_plan__state=0)| Q(production_plan__state__isnull=True)).exists()

    @property
    def order_nr(self):
        """
        Return an order number for a given basket
        """
        return 100000 + self.pk

    @property
    def has_abo(self):
        return self.positions.filter(customer_order_template_positions__isnull=False).exists()
    
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
            defaults={
                'quantity': quantity,
            }
        )
        if not created:
            position.quantity = (position.quantity or 0) + quantity
            position.save(update_fields=['quantity'])
            
        return created_order


    @classmethod
    def create_or_update_customer_order(cls, production_day, customer, products, point_of_sale=None):
        # TODO order_nr, address, should point of sale really be saved in order?
        point_of_sale = point_of_sale and PointOfSale.objects.get(pk=point_of_sale) or customer.point_of_sale
        customer_order, created = CustomerOrder.objects.update_or_create(
            production_day=production_day,
            customer=customer,
            defaults={
                'point_of_sale': point_of_sale,
            }
        )
        for product, quantity in products.items():
            production_day_product = ProductionDayProduct.objects.get(production_day=production_day, product=product)
            if production_day_product.is_locked:
                raise forms.ValidationError("Product is locked.")
            if quantity > 0:
                price = None
                price_total = None
                if product.sale_price:
                    price = product.sale_price.price.amount
                    price_total = price * quantity
                position, created = CustomerOrderPosition.objects.update_or_create(
                    order=customer_order,
                    product=product,
                    defaults={
                        'quantity': quantity,
                        'price': price,
                        'price_total': price_total,
                    }
                )
            elif quantity == 0:
                CustomerOrderPosition.objects.filter(
                    order=customer_order,
                    product=product
                ).delete()
            
        if CustomerOrderPosition.objects.filter(order=customer_order).count() == 0:
            customer_order.delete()
            return None
        return customer_order
    
    def get_production_day_products_ordered_list(self):
        production_day_products = self.production_day.production_day_products.published()
        production_day_products = production_day_products.annotate(
            ordered_quantity=Subquery(self.positions.filter(Q(product=OuterRef('product__pk')) | Q(product__product_template=OuterRef('product__pk')),).values("quantity"))
        ).annotate(
                price=Subquery(CustomerOrderPosition.objects.filter(order__customer=self.customer, order__production_day=self.production_day, product=OuterRef('product__pk')).values("price_total"))
        ).annotate(
                price=Subquery(CustomerOrderPosition.objects.filter(order__customer=self.customer, order__production_day=self.production_day, product=OuterRef('product__pk')).values("price_total"))
        ).annotate(
            has_abo=Exists(Subquery(CustomerOrderTemplatePosition.objects.active().filter(order_template__customer=self.customer, product=OuterRef('product__pk'))))
        ).annotate(
            abo_qty=Subquery(CustomerOrderTemplatePosition.objects.active().filter(
                Q(orders__product=OuterRef('product__pk')) | Q(orders__product__product_template=OuterRef('product__pk')),
                orders__order__pk=self.pk,
                orders__order__customer=self.customer,
                ).values("quantity")
            )
        )
        return production_day_products

    def replace_message_tags(self, message, request):
        t = Template(message)
        client = request.tenant
        message = t.render(Context({
            'site_name': client.name,
            'first_name': self.customer.user.first_name,
            'last_name': self.customer.user.last_name,
            'email': self.customer.user.email,
            'order': self.get_order_positions_string(),
            'production_day': self.production_day.day_of_sale.strftime('%d.%m.%Y'),
            'order_count': self.total_quantity,
            'order_link': request.build_absolute_uri("{}#bestellung-{}".format(reverse_lazy('shop:order-list'), self.pk)),
        }))
        return message

    def send_order_confirm_email(self, request):
        from bakeup.pages.models import EmailSettings
        try:
            email_settings = EmailSettings.load(request_or_site=request)
            user_email = self.customer.user.email
            message_body = self.replace_message_tags(email_settings.get_body_with_footer(email_settings.email_order_confirm), request)
            message_subject = self.replace_message_tags(email_settings.get_subject_with_prefix(email_settings.email_order_confirm_subject), request)
            send_mail(
                message_subject,
                message_body,
                settings.DEFAULT_FROM_EMAIL,
                [user_email],
                fail_silently=False,
            )
        except Exception as e:
            logger.exception('Sending order confirm email failed.', stack_info=True)



class CustomerOrderPositionQuerySet(models.QuerySet):
    def produced(self):
        return self.filter(production_plan__state=ProductionPlan.State.PRODUCED)


class BasePositionClass(CommonBaseClass):
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='%(class)s_positions')
    quantity = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True


class CustomerOrderPosition(BasePositionClass):
    order = models.ForeignKey('shop.CustomerOrder', on_delete=models.CASCADE, related_name='positions')
    production_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    is_paid = models.BooleanField(default=False)
    is_picked_up = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    price = MoneyField(blank=True, null=True, max_digits=14, decimal_places=2, default_currency='EUR')
    price_total = MoneyField(blank=True, null=True, max_digits=14, decimal_places=2, default_currency='EUR')

    objects = CustomerOrderPositionQuerySet.as_manager()

    class Meta:
        ordering = ['product']

    
class CustomerOrderTemplatePositionQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        qs = self.filter(
            order_template__parent__isnull=True,
            order_template__start_date__lte=now)
        qs = qs.filter(Q(order_template__end_date__gte=now) | Q(order_template__end_date__isnull=True))
        return qs


class CustomerOrderTemplatePosition(BasePositionClass):
    order_template = models.ForeignKey('shop.CustomerOrderTemplate', on_delete=models.CASCADE, related_name='positions')
    orders = models.ManyToManyField('shop.CustomerOrderPosition', related_name='customer_order_template_positions')

    objects = CustomerOrderTemplatePositionQuerySet.as_manager()

    def create_order(self, production_day):
        with transaction.atomic():
            customer_order, created = CustomerOrder.objects.update_or_create(
                production_day=production_day,
                customer=self.order_template.customer,
                defaults={
                    'point_of_sale': self.order_template.customer.point_of_sale
                }
            )
            position = CustomerOrderPosition.objects.create(
                order=customer_order,
                product=self.product,
                quantity=self.quantity,
            )
            self.orders.add(position)
            self.order_template.set_locked()
        from bakeup.pages.models import EmailSettings
        if EmailSettings.load(request_or_site=request).send_email_order_confirm:
            order.send_order_confirm_email(request)

    def cancel(self):
        with transaction.atomic():
            template_order = self.order_template.prepare_update()
            template_order.positions.filter(product=self.product).delete()
            if not template_order.positions.exists():
                template_order.cancel()
            return template_order
    

class CustomerOrderTemplateQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        qs = self.filter(
            parent__isnull=True,
            start_date__lte=now)
        qs = qs.filter(Q(end_date__gte=now) | Q(end_date__isnull=True))
        return qs    


class CustomerOrderTemplate(CommonBaseClass):
    parent = models.OneToOneField('self', blank=True, null=True, related_name='child', on_delete=models.SET_NULL)
    customer = models.ForeignKey('shop.Customer', on_delete=models.PROTECT, related_name='order_templates')
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    is_locked = models.BooleanField(default=False)

    objects = CustomerOrderTemplateQuerySet.as_manager()

    @property
    def is_running(self):
        if self.start_date <= timezone.now():
            if not self.end_date or self.end_date >= timezone.now():
                return True
        return False


    def get_state(self):
        if self.is_running:
            return _('running')
        return _('finished')

    def set_locked(self):
        if not self.is_locked:
            self.is_locked = True
            self.save(update_fields=['is_locked', 'updated'])

    def cancel(self):
        self.end_date = timezone.now()
        self.save(update_fields=['end_date', 'updated'])

    def prepare_update(self):
        if self.is_locked or not self.is_running:
            self.end_date = timezone.now()
            order_template = CustomerOrderTemplate.objects.create(
                customer=self.customer,
                start_date=timezone.now(),
                is_locked=False
            )
            for position in self.positions.all():
                CustomerOrderTemplatePosition.objects.create(
                    order_template=order_template,
                    product=position.product,
                    quantity=position.quantity,
                )
            self.parent = order_template
            self.save()
            return order_template
        else:
            return self

    @classmethod
    def create_customer_order_template(cls, request, customer, products):
        order_template, created = CustomerOrderTemplate.objects.get_or_create(
            parent=None,
            customer=customer,
            defaults={
                'start_date': timezone.now(),
            }
        )
        # raise Exception('here')
        if products:
            order_template = order_template.prepare_update()
        for product, quantity in products.items():
            exisitng_position = CustomerOrderTemplatePosition.objects.filter(
                order_template=order_template,
                product=product,
            )
            if quantity == 0 and exisitng_position.exists():
                CustomerOrderTemplatePosition.objects.filter(
                    order_template=order_template,
                    product=product,
                ).first().cancel()
                continue
            if product.is_open_for_abo:
                existing_abo_qty = 0
                if exisitng_position.exists():
                    existing_abo_qty = exisitng_position.first().quantity
                if product.available_abo_quantity and quantity > (product.available_abo_quantity + existing_abo_qty):
                    quantity = product.available_abo_quantity
                    messages.add_message(request, messages.INFO, f"Es sind nicht mehr genügend Abo Plätze verfügbar. Es wurde eine kleinere Menge von {product.name } abonniert.")
                CustomerOrderTemplatePosition.objects.update_or_create(
                    order_template=order_template,
                    product=product,
                    defaults={
                        'quantity': quantity,
                    }
                )
        return order_template

        
    


    




# class ProductionDay