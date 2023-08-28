from datetime import datetime

from django.utils.translation import gettext_lazy as _
from django.db import models
from django.db.models import F, Func, Value, CharField, PositiveSmallIntegerField, Q
from django.db.models import OuterRef, Subquery
from django.db.models import Case, When, Value, IntegerField, Exists
from django.template.loader import render_to_string

from wagtail import blocks
from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import (
    BaseGenericSetting,
    BaseSiteSetting,
    register_setting,
)

from bakeup.shop.models import CustomerOrder,  ProductionDay,  PointOfSale, ProductionDayProduct, CustomerOrderPosition, CustomerOrderTemplatePosition
from bakeup.pages.blocks import AllBlocks, ButtonBlock, ContentBlocks

# Create your models here.
class ContentPage(Page):
    content = StreamField(AllBlocks(), blank=True, null=True, use_json_field=True)

    parent_page_types = ['pages.ShopPage']
    preview_modes = []
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
    preview_modes = []
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
            current_customer_order = CustomerOrder.objects.filter(customer=customer, production_day=self.production_day).first()
            context['current_customer_order'] = current_customer_order
            production_day_products = self.production_day.production_day_products.published()
            # TODO this needs to go at one place, code duplication, very bad idea shop/views
            production_day_products = production_day_products.annotate(
                ordered_quantity=Subquery(
                    CustomerOrderPosition.objects.filter(
                        Q(product=OuterRef('product__pk')) | Q(product__product_template=OuterRef('product__pk')),
                        order__customer=customer, 
                        order__production_day=self.production_day, 
                    ).values("quantity")
                )
            ).annotate(
                price=Subquery(
                    CustomerOrderPosition.objects.filter(
                        Q(product=OuterRef('product__pk')) | Q(product__product_template=OuterRef('product__pk')),
                        order__customer=customer, 
                        order__production_day=self.production_day, 
                    ).values("price_total")
                )
            ).annotate(
               has_abo=Exists(Subquery(CustomerOrderTemplatePosition.objects.active().filter(
                    Q(product=OuterRef('product__pk')) | Q(product__product_template=OuterRef('product__pk')),
                    order_template__customer=customer, 
                )))
            )
            if current_customer_order:
                production_day_products = production_day_products.annotate(
                    abo_qty=Subquery(CustomerOrderTemplatePosition.objects.active().filter(
                        Q(orders__product=OuterRef('product__pk')) | Q(orders__product__product_template=OuterRef('product__pk')),
                        orders__order__pk=current_customer_order.pk,
                        orders__order__customer=customer,
                        ).values("quantity")
                    )
                )
            context['production_day_products'] = production_day_products
        context['show_remaining_products'] = request.tenant.clientsetting.show_remaining_products
        context['point_of_sales'] = PointOfSale.objects.all()
        context['all_production_days'] = list(ProductionDay.objects.published().annotate(
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
    footer = StreamField(ContentBlocks(), blank=True, null=True, use_json_field=True)


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


@register_setting(icon='key')
class GeneralSettings(BaseGenericSetting):
    class Visibility(models.TextChoices):
        NEVER = "never", "Never"
        ALWAYS = "always", "Always"
        AUTOMATICALLY = "automatically", "Automatically"
    class FontStyle(models.TextChoices):
        HANDWRITING = "font-handwriting", "Handwriting"
        SERIF = "font-quattrocento", "Serif (quattrocento)"
        SANS_SERIF = "font-sans-serif", "Sans Serif"
    abo_menu_item = models.CharField(max_length=13, default=Visibility.AUTOMATICALLY, choices=Visibility.choices, help_text="Soll der Abo Menüpunkt angezeigt werden?")
    brand_font = models.CharField(max_length=17, default=FontStyle.HANDWRITING, choices=FontStyle.choices, help_text="Welche Schriftart soll der brand name in der Mobilen ansicht haben?")
    brand_uppercase = models.BooleanField(default=False, help_text="Brand name in Großbuchstaben")

    panels = [
        FieldPanel('abo_menu_item'),
        MultiFieldPanel([
            FieldPanel('brand_font'),
            FieldPanel('brand_uppercase'),
        ], heading='Brand name')
    ]
    class Meta:
        verbose_name = "General settings"


@register_setting(icon='user')
class CheckoutSettings(BaseGenericSetting):
    order_button_place = models.CharField(max_length=1024, default='Jetzt kostenpflichtig bestellen', verbose_name='Button bestellen')
    order_button_change = models.CharField(max_length=1024, default='Jetzt verbindlich ändern', verbose_name='Button Bestellung ändern')
    order_button_cancel = models.CharField(max_length=1024, default='Bestellung komplett stornieren', verbose_name='Button Bestellung stornieren')
    terms_and_conditions_show = models.BooleanField(default=False, verbose_name='Checkbox AGB anzeigen?')
    terms_and_conditions_text = RichTextField(blank=True, null=True, verbose_name='AGB Text')
    
    panels = [
        FieldPanel('order_button_place'),
        FieldPanel('order_button_change'),
        FieldPanel('order_button_cancel'),
        MultiFieldPanel([
            FieldPanel('terms_and_conditions_show'),
            FieldPanel('terms_and_conditions_text'),
        ], heading='AGB')
    ]
    class Meta:
        verbose_name = "Checkout settings"


def get_production_day_reminder_body():
    return render_to_string('users/emails/production_day_reminder_body.txt', {'client': '{{ client }}', 'user': '{{ user }}', 'order': '{{ order }}', 'price_total': '{{ price_total }}'})


@register_setting(icon='mail')
class EmailSettings(BaseGenericSetting):
    email_subject_prefix = models.CharField(max_length=1024, default="[{{site_name}}]", help_text="E-Mail-Betreff Präfix, kann {{site_name}} enthalten.")
    email_footer = models.TextField(blank=True, null=True, help_text="Dieser Footer wird an jede Email angehängt.")
    send_email_order_confirm = models.BooleanField(default=False, help_text='Soll eine Bestellbestätigungsmail versendet werden?', verbose_name='Bestellbestätigung versenden?')
    email_order_confirm_subject = models.CharField(default='Vielen Dank für Deine Bestellung', max_length=1024, help_text="Betreff Bestellbestätigungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}, {{ order_link }}")
    email_order_confirm = models.TextField(blank=True, null=True, help_text="Bestellbestätigungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ price_total }}, {{ production_day }}, {{ order_count }}, {{ order_link }}, {{ point_of_sale }}")
    email_order_confirm_attachment = models.ForeignKey(
        'wagtaildocs.Document',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name='Attachment'
    )
    production_day_reminder_subject = models.CharField(default='Deine Bestellung ist abholbereit', max_length=1024, help_text="Betreff Erinnerungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}")
    production_day_reminder_body = models.TextField(default=get_production_day_reminder_body, help_text="Erinnerungs E-Mail. Mögliche Tags: {{ site_name }}, {{ first_name }}, {{ last_name }}, {{ email }}, {{ order }}, {{ production_day }}, {{ order_count }}")

    
    panels = [
        FieldPanel('email_subject_prefix'),
        FieldPanel('email_footer'),
        MultiFieldPanel([
            FieldPanel('send_email_order_confirm'),
            FieldPanel('email_order_confirm_subject'),
            FieldPanel('email_order_confirm'),
            FieldPanel('email_order_confirm_attachment'),
        ], heading='Bestellbestätigung'),
        MultiFieldPanel([
            FieldPanel('production_day_reminder_subject'),
            FieldPanel('production_day_reminder_body'),
        ], heading='Bestellerinnerung')
    ]
    class Meta:
        verbose_name = "E-Mail settings"

    def get_subject_with_prefix(self, subject):
        if self.email_subject_prefix:
            return "{} {}".format(self.email_subject_prefix, subject)
        else:
            return subject

    def get_body_with_footer(self, body):
        if self.email_footer:
            return "{}\n\n{}".format(body, self.email_footer)
        else:
            return body
