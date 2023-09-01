import logging 
import collections

from django.contrib.postgres.aggregates.general import ArrayAgg
from django.urls import reverse_lazy
from django.core.mail import EmailMessage
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
from django.utils.translation import gettext_lazy as _

from djmoney.money import Money
from djmoney.models.fields import MoneyField
from recurrence.fields import RecurrenceField

from bakeup.core.models import CommonBaseClass
from bakeup.workshop.models import Product, ProductionPlan


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
    def planned(self):
        return self.filter(Q(production_day_products__production_plan__state=0)| Q(production_day_products__production_plan__isnull=True))

    def published(self):
        return self.filter(production_day_products__is_published=True).distinct()

    def upcoming(self):
        today = timezone.now().date()
        return self.filter(day_of_sale__gte=today).order_by('day_of_sale')


class ProductionDay(CommonBaseClass):
    day_of_sale = models.DateField(unique=True, verbose_name=_("Day of Sale"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))

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

    @property
    def total_ordered_quantity(self):
        return CustomerOrderPosition.objects.filter(order__production_day=self).aggregate(Sum('quantity'))['quantity__sum']
    
    @property
    def total_published_ordered_quantity(self):
        return CustomerOrderPosition.objects.filter(order__production_day=self, product__in=self.production_day_products.filter(is_published=True).values_list('product', flat=True)).aggregate(Sum('quantity'))['quantity__sum']
    
    def update_production_plan(self, product, quantity, state, create_max_quantity):
        ProductionPlan.objects.filter(product__product_template=product, production_day=self).delete()
        return self._create_production_plan(product, quantity, state, create_max_quantity)

    def _create_production_plan(self, product, quantity, state, create_max_quantity=False):
        # product_product_quantity.get('product'), product_quantity.get('total_quantity')
        product_template = product
        if quantity == 0:
            # if no orders, plan is cancelled
            state = ProductionPlan.State.CANCELED
        production_plan = ProductionPlan.objects.filter(production_day=self, parent_plan=None, product__product_template=product_template)
        if production_plan.exists() and not production_plan.first().is_locked:
            print('plan exists, plan update: {}'.format(product_template))
            return self.update_production_plan(product_template, quantity, state, create_max_quantity)
        elif production_plan.exists():
            # plan is locked no update
            print('plan exists: {}'.format(product_template))
            return production_plan.first()
        print('plan create: {}'.format(product_template))
        # this needs to happen before duplicating!
        production_day_product = ProductionDayProduct.objects.get(product=product, production_day=self)
        product = Product.duplicate(product_template)
        obj = ProductionPlan.objects.create(
            parent_plan=None,
            production_day=self,
            product=product,
            quantity=quantity,
            start_date=self.day_of_sale,
            state=state,
        )
        # raise Exception(product.pk, product_template.pk)
        if quantity > 0:
            ProductionPlan.create_all_child_plans(obj, obj.product.parents.all(), quantity_parent=quantity)
        production_day_product.production_plan = obj
        production_day_product.save()
        return obj

    def create_or_update_production_plan(self, product, state, create_max_quantity=False):
        if create_max_quantity:
            quantity = self.production_day_products.get(product=product).max_quantity
        else:
            positions = CustomerOrderPosition.objects.filter(
                Q(product=product) | Q(product__product_template=product),
                order__production_day=self, 
            )
            quantity = positions.values('product', 'product__product_template').aggregate(total_quantity=Sum('quantity')).get('total_quantity') or 0
        plan = self._create_production_plan(product, quantity, state, create_max_quantity)
        if positions:
            positions.update(production_plan=plan)
        return plan


    def create_or_update_production_plans(self, state, create_max_quantity=False):
        plans = []
        positions = None
        if create_max_quantity:
            product_quantities = self.production_day_products.values('product', total_quantity=F('max_quantity'))
        else:
            positions = CustomerOrderPosition.objects.filter(
                order__production_day=self, 
            )
            product_quantities = positions.values('product', 'product__product_template').order_by('product').annotate(total_quantity=Sum('quantity'))
        for product_quantity in product_quantities:
            product = Product.objects.get(pk=product_quantity.get('product'))
            plan = self._create_production_plan(product, product_quantity.get('total_quantity'), state, create_max_quantity)
            if positions:
                positions.update(production_plan=plan)
            plans.append(plan)
        return plans
            

    def create_template_orders(self, request):
        production_day_products = self.production_day_products.published().values_list('product', flat=True)
        order_templates = CustomerOrderTemplate.objects.active().filter(positions__product__in=production_day_products)
        for order_template in order_templates:
            customer_order_template_positions = order_template.positions.filter(product__in=production_day_products)
            CustomerOrderTemplate.create_abo_orders_for_production_days(order_template.customer, customer_order_template_positions, [self], request)

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
            Q(product=production_plan_product.product_template) | Q(product__product_template=production_plan_product.product_template),
            order__production_day=self,
        )
        positions.update(product=production_plan_product)

class ProductionDayProductQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)
    
    def upcoming(self):
        today = timezone.now().date()
        return self.filter(production_day__day_of_sale__gte=today).order_by('production_day__day_of_sale')

    def planned(self):
        return self.filter(Q(production_plan__state=0)| Q(production_plan__isnull=True))
    
    def with_pictures(self):
        return self.exclude(
            Q(product__image='')|
            Q(product__image=None))


class ProductionDayProduct(CommonBaseClass):
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.CASCADE, related_name='production_day_products')
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='production_days', limit_choices_to={'is_sellable': True}, verbose_name=_("Product"))
    max_quantity = models.PositiveSmallIntegerField(blank=False, null=False, verbose_name=_("Max quantity"))
    production_plan = models.ForeignKey('workshop.ProductionPlan', on_delete=models.SET_NULL, blank=True, null=True)
    is_published = models.BooleanField(default=False, verbose_name=_("Published?"))
    
    objects = ProductionDayProductQuerySet.as_manager()

    class Meta:
        ordering = ('production_day', 'product')
        unique_together = ['production_day', 'product']

    def __str__(self):
        return "{}: {}".format(self.production_day, self.product)

    @classmethod
    def get_available_abo_product_days(cls, production_day, customer):
        production_day_products = cls.objects.published().upcoming().planned().filter(
                product__is_recurring=True
            ).annotate(
                has_order=Exists(Subquery(
                    CustomerOrderPosition.objects.filter(
                        Q(product=OuterRef('product')) | Q(product__product_template=OuterRef('product')),
                        order__customer=customer, 
                        order__production_day=OuterRef('production_day'), 
                    ))
                )
            ).exclude(
                production_day=production_day,
            ).filter(
                has_order=False
            ).distinct()
        result = collections.defaultdict(dict)
        for production_day_product in production_day_products:
            production_days = result[production_day_product.product.pk]
            production_days["{}".format(production_day_product.production_day.day_of_sale)] = production_day_product.calculate_max_quantity()
        return result

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
            Q(product=self.product) | Q(product__product_template=self.product),
            order__production_day=self.production_day
        )
        return orders.aggregate(quantity_sum=Sum('quantity'))['quantity_sum'] or 0

    def calculate_max_quantity(self, exclude_customer=None):
        orders = CustomerOrderPosition.objects.filter(
            Q(product=self.product) | Q(product__product_template=self.product),
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
    production_day = models.ForeignKey('shop.ProductionDay', on_delete=models.PROTECT, related_name='customer_orders', verbose_name=_('Production Day'))
    customer = models.ForeignKey('shop.Customer', on_delete=models.PROTECT, blank=True, null=True, related_name='orders', verbose_name=_('Customer'))
    point_of_sale = models.ForeignKey('shop.PointOfSale', on_delete=models.SET_NULL, blank=True, null=True, related_name='customer_orders', verbose_name=_('Point of Sale'))
    address = models.TextField()

    class Meta:
        unique_together = ['production_day', 'customer']
        ordering = ['production_day', '-created']

    def __str__(self):
        return "{} {}".format(self.production_day, self.customer)
    
    def get_order_positions_string(self):
        positions_string = ""
        for position in self.positions.all():
            price_total = ''
            if position.price_total:
                price_total = " {}".format(position.price_total)
            positions_string += "{}x {}{}".format(position.quantity, position.product.get_display_name(), price_total) + "\n"
        return positions_string
    
    @property
    def price_total(self):
        return self.positions.aggregate(price_total=Sum('price_total', default=0))['price_total']

    @property
    def total_quantity(self):
        return self.positions.aggregate(total_quantity=Sum('quantity'))['total_quantity']

    @property
    def is_picked_up(self):
        return not self.positions.filter(is_picked_up=False).exists()

    @property
    def is_locked(self):
        return not self.positions.filter(Q(production_plan__state=0)| Q(production_plan__isnull=True)).exists()

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
    def create_or_update_customer_order(cls, production_day, customer, products, point_of_sale=None):
        # TODO order_nr, address, should point of sale really be saved in order?
        # TODO check quantity with availalbe quantity
        with transaction.atomic():
            point_of_sale = point_of_sale and PointOfSale.objects.get(pk=point_of_sale) or customer.point_of_sale
            customer_order, created = CustomerOrder.objects.update_or_create(
                production_day=production_day,
                customer=customer,
                defaults={
                    'point_of_sale': point_of_sale,
                }
            )
            for product, quantity in products.items():
                # print(product, quantity)
                production_day_product = ProductionDayProduct.objects.get(production_day=production_day, product=product)
                max_quantity = production_day_product.calculate_max_quantity(customer)
                if production_day_product.is_locked or max_quantity == 0:
                    raise forms.ValidationError("Product is locked.")
                if quantity > 0:
                    quantity = min(quantity, max_quantity)
                    price = None
                    price_total = None
                    if product.sale_price:
                        price = product.sale_price.price.amount
                        price_total = price * quantity
                    position, created = CustomerOrderPosition.objects.filter(
                        Q(product=product) | Q(product__product_template=product)
                    ).update_or_create(
                        order=customer_order,
                        defaults={
                            'product': product,
                            'quantity': quantity,
                            'price': price,
                            'price_total': price_total,
                        }
                    )
                elif quantity == 0:
                    CustomerOrderPosition.objects.filter(
                        Q(product=product) | Q(product__product_template=product),
                        order=customer_order
                    ).delete()
                
            if CustomerOrderPosition.objects.filter(order=customer_order).count() == 0:
                customer_order.delete()
                return None, None
            return customer_order, created
    
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
            'price_total': self.price_total and Money(self.price_total, 'EUR') or '',
            'production_day': self.production_day.day_of_sale.strftime('%d.%m.%Y'),
            'order_count': self.total_quantity,
            'order_link': request.build_absolute_uri("{}#bestellung-{}".format(reverse_lazy('shop:order-list'), self.pk)),
            'point_of_sale': self.point_of_sale,
        }))
        return message

    def send_order_confirm_email(self, request):
        from bakeup.pages.models import EmailSettings
        try:
            email_settings = EmailSettings.load(request_or_site=request)
            user_email = self.customer.user.email
            message_body = self.replace_message_tags(email_settings.get_body_with_footer(email_settings.email_order_confirm), request)
            message_subject = self.replace_message_tags(email_settings.get_subject_with_prefix(email_settings.email_order_confirm_subject), request)
            message = EmailMessage(
                message_subject,
                message_body,
                settings.DEFAULT_FROM_EMAIL,
                [user_email],
            )
            if email_settings.email_order_confirm_attachment:
                message.attach(email_settings.email_order_confirm_attachment.title, email_settings.email_order_confirm_attachment.file.read(), 'application/pdf')
            message.send(fail_silently=False) 
        except Exception as e:
            logger.exception('Sending order confirm email failed.', stack_info=True)



class CustomerOrderPositionQuerySet(models.QuerySet):
    def produced(self):
        return self.filter(production_plan__state=ProductionPlan.State.PRODUCED)


class BasePositionClass(CommonBaseClass):
    product = models.ForeignKey('workshop.Product', on_delete=models.PROTECT, related_name='%(class)s_positions', verbose_name=_('Product'))
    quantity = models.PositiveSmallIntegerField(verbose_name=_('Quantity'))
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
    def create_abo_orders_for_production_days(cls, customer, customer_order_template_positions, production_days, request):
        # TODO its a bit ugly to loop the request object till here. maybe this should go somewhere else
        with transaction.atomic():
            # TODO check if its ok without .exclude(production_day=production_day)
            for production_day in production_days:
                is_order_created = False
                for customer_order_template_position in customer_order_template_positions:
                    product = customer_order_template_position.product
                    customer_order = CustomerOrderPosition.objects.filter(
                        Q(product=product) | Q(product__product_template=product),
                        order__production_day=production_day,
                        order__customer=customer
                    )
                    production_day_product = production_day.production_day_products.filter(product=product)
                    if not customer_order.exists() and production_day_product:
                        production_day_product = production_day_product.get()
                        customer_order, created = CustomerOrder.objects.get_or_create(
                            production_day=production_day,
                            customer=customer,
                            defaults={
                                'point_of_sale': customer.point_of_sale,
                            }
                        )
                        max_quantity = production_day_product.calculate_max_quantity(customer)
                        quantity = min(customer_order_template_position.quantity, max_quantity)
                        if not production_day_product.is_locked and quantity > 0:
                            print('Create Abo order: ', production_day, product, quantity)
                            price = None
                            price_total = None
                            if product.sale_price:
                                price = product.sale_price.price.amount
                                price_total = price * quantity
                            position = CustomerOrderPosition.objects.create(
                                order=customer_order,
                                product=product,
                                quantity=quantity,
                                price=price,
                                price_total=price_total,
                            )
                            customer_order_template_position.orders.add(position)
                            customer_order_template_position.order_template.set_locked()
                            is_order_created = True
                from bakeup.pages.models import EmailSettings
                if is_order_created and EmailSettings.load(request_or_site=request).send_email_order_confirm:
                    customer_order.send_order_confirm_email(request)

    @classmethod
    def create_customer_order_template(cls, request, customer, products, production_day=None, create_future_production_day_orders=False):
        order_template, created = CustomerOrderTemplate.objects.get_or_create(
            parent=None,
            customer=customer,
            defaults={
                'start_date': timezone.now(),
            }
        )
        # raise Exception('here')
        customer_order_template_positions = []
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
                order_template_position, created = CustomerOrderTemplatePosition.objects.update_or_create(
                    order_template=order_template,
                    product=product,
                    defaults={
                        'quantity': quantity,
                    }
                )
                customer_order_template_positions.append(order_template_position)
        if create_future_production_day_orders and customer_order_template_positions:
            # create orders for all planned future production days
            production_days = ProductionDay.objects.published().upcoming().planned().filter(
                production_day_products__product__in=[position.product.pk for position in customer_order_template_positions]
            ).distinct()
            CustomerOrderTemplate.create_abo_orders_for_production_days(customer, customer_order_template_positions, production_days, request)

        return order_template

        
    


    




# class ProductionDay