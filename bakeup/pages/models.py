from datetime import datetime

from django.utils.translation import gettext_lazy as _
from django.db import models
from django.db.models import F, Func, Value, CharField, PositiveSmallIntegerField
from django.db.models import OuterRef, Subquery

from wagtail import blocks
from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import (
    BaseGenericSetting,
    BaseSiteSetting,
    register_setting,
)

from bakeup.shop.models import CustomerOrder,  ProductionDay,  PointOfSale, ProductionDayProduct, CustomerOrderPosition
from bakeup.pages.blocks import AllBlocks, ButtonBlock, ContentBlocks

# Create your models here.
class ContentPage(Page):
    content = StreamField(AllBlocks(), blank=True, null=True, use_json_field=True)

    parent_page_types = ['pages.ShopPage']
    show_in_menus_default = True
    content_panels = Page.content_panels + [
        FieldPanel("content"),
    ]


class ShopPage(Page):
    banner_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Image'
    )
    banner_text = RichTextField(blank=True, verbose_name='Text')
    banner_cta = StreamField([('buttons', ButtonBlock()),], verbose_name='Call to action', blank=True, null=True, use_json_field=True)

    text_no_production_day = RichTextField(blank=True, verbose_name=_('No production days planned'), help_text="This text is displayed if no production day is planned.")
    content = StreamField(AllBlocks(), blank=True, null=True, use_json_field=True)

    parent_page_types = ['wagtailcore.Page']
    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('banner_image'),
            FieldPanel('banner_text'),
            FieldPanel('banner_cta'),
        ], heading="Banner"),
        MultiFieldPanel([
            FieldPanel('text_no_production_day'),
        ], heading="Production Day"),
        FieldPanel('content'),
    ]

    def get_production_day(self, *args, **kwargs):
        today = datetime.now().date()
        production_day_next = ProductionDayProduct.objects.filter(
            is_published=True, 
            production_day__day_of_sale__gte=today).order_by('production_day__day_of_sale').first()
        if production_day_next:
            return production_day_next.production_day
        return None

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        self.production_day = self.get_production_day(*args, **kwargs)
        customer = None if request.user.is_anonymous else request.user.customer
        context['production_days'] = ProductionDay.objects.upcoming()
        if self.production_day:
            context['production_days'] = context['production_days'].exclude(id=self.production_day.pk)
            context['production_day_next'] = self.production_day
            context['current_customer_order'] = CustomerOrder.objects.filter(customer=customer, production_day=self.production_day).first()
            production_day_products = self.production_day.production_day_products.published()
            production_day_products = production_day_products.annotate(
                ordered_quantity=Subquery(CustomerOrderPosition.objects.filter(order__customer=customer, order__production_day=self.production_day, product=OuterRef('product__pk')).values("quantity"))
            )
            context['production_day_products'] = production_day_products
        context['show_remaining_products'] = request.tenant.clientsetting.show_remaining_products
        context['point_of_sales'] = PointOfSale.objects.all()
        context['all_production_days'] = list(ProductionDay.objects.filter(production_day_products__is_published=True).annotate(
            formatted_date=Func(
                F('day_of_sale'),
                Value('dd.MM.yyyy'),
                function='to_char',
                output_field=CharField()
            )
        ).values_list('formatted_date', flat=True))
        return context
    

@register_setting
class FooterSettings(BaseGenericSetting):
    footer = StreamField(ContentBlocks(), blank=True, null=True)


@register_setting(icon='success')
class BrandSettings(BaseGenericSetting):

    logo = models.ForeignKey(
        'wagtailimages.Image',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Image'
    )
    is_brand_theme_activated = models.BooleanField(default=False, verbose_name='Theme activated?')
    primary_color = models.CharField(max_length=8, verbose_name='Primary color', help_text="as a hex value", blank=True, null=True)
    secondary_color = models.CharField(max_length=8, verbose_name='Secondary color', help_text="as a hex value", blank=True, null=True)
    light_color = models.CharField(max_length=8, verbose_name='Light color', help_text="as a hex value", blank=True, null=True)
    dark_color = models.CharField(max_length=8, verbose_name='Dark color', help_text="as a hex value", blank=True, null=True)
    
    panels = [
        FieldPanel('logo'),
        MultiFieldPanel([
            FieldPanel('is_brand_theme_activated'),
            FieldPanel('primary_color'),
            FieldPanel('secondary_color'),
            FieldPanel('light_color'),
            FieldPanel('dark_color'),
        ], heading='Theme')
    ]
    class Meta:
        verbose_name = "Brand settings"


@register_setting(icon='user')
class CheckoutSettings(BaseGenericSetting):
    order_button_place = models.CharField(max_length=1024, default='Jetzt kostenpflichtig bestellen', verbose_name='Button bestellen')
    order_button_change = models.CharField(max_length=1024, default='Jetzt kostenpflichtig ändern', verbose_name='Button Bestellung ändern')
    terms_and_conditions_show = models.BooleanField(default=False, verbose_name='Checkbox AGB anzeigen?')
    terms_and_conditions_text = RichTextField(blank=True, null=True, verbose_name='AGB Text')
    
    panels = [
        FieldPanel('order_button_place'),
        FieldPanel('order_button_change'),
        MultiFieldPanel([
            FieldPanel('terms_and_conditions_show'),
            FieldPanel('terms_and_conditions_text'),
        ], heading='AGB')
    ]
    class Meta:
        verbose_name = "Checkout settings"

