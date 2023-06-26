from unicodedata import category
from django.forms import BooleanField, CharField, DecimalField, FloatField, IntegerField, ModelChoiceField, ModelForm, Form, Textarea, formset_factory, BaseFormSet
from django.db.models import Q
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from bakeup.shop.models import ProductionDay, Customer

from bakeup.shop.models import PointOfSale
from bakeup.workshop.models import Category, Product, ProductHierarchy, ProductionPlan, ReminderMessage


class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'display_name', 'sku', 'description', 'image', 'image_secondary', 'category', 'tags', 'weight', 'is_sellable', 'is_buyable', 'is_composable']


class AddProductForm(Form):
    weight = FloatField(required=False)
    product_existing = ModelChoiceField(queryset=Product.objects.all(), required=False, empty_label="Select existing product")
    product_new = CharField(required=False, label="New product name")
    category = ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label="Select a category")
    is_sellable = BooleanField(label='Sellable?', required=False)
    is_buyable = BooleanField(label='Buyable?', required=False)
    is_composable = BooleanField(label='Composable?', required=False)

    def __init__(self, product=None, parent_products=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        products = Product.objects.filter(
            Q(category__path__startswith=Category.objects.get(slug='dough').path) | 
            Q(category__path__startswith=Category.objects.get(slug='preparations').path) |
            Q(category__path__startswith=Category.objects.get(slug='ingredients').path)
        )
        if parent_products:
            products = products.exclude(pk__in=parent_products.values_list('parent__pk', flat=True))
        if product:
            products = products.exclude(pk=product.pk)
        self.fields['product_existing'].queryset = products

AddProductFormSet = formset_factory(AddProductForm, extra=0)


class SelectProductForm(Form):
    product = ModelChoiceField(queryset=Product.objects.all())


class ProductHierarchyForm(Form):
    amount = FloatField(localize=True)


class ProductionPlanDayForm(Form):
    production_day = ModelChoiceField(queryset=ProductionDay.objects.all(), widget=forms.Select(attrs={"onchange":'this.form.submit()', "class": 'form-select'}))


class ProductionPlanForm(ModelForm):
    class Meta:
        model = ProductionPlan
        fields = ('start_date', 'duration')


class ProductKeyFiguresForm(Form):
    fermentation_loss = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Gärverlust', localize=True)
    dough_yield = IntegerField(min_value=100, label='TA', disabled=True, required=False)
    salt = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Salz', disabled=True, required=False, localize=True)
    starter = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Starter', disabled=True, required=False)
    wheat = CharField(label='Mehl', disabled=True, required=False, widget=Textarea(attrs={'rows':2,}))
    pre_ferment = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Ferment. Mehlmenge', disabled=True, required=False, localize=True)
    total_dough_weight = DecimalField(decimal_places=2, min_value=0, label='Teiggewicht', disabled=True, required=False, localize=True)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'initial' in kwargs and 'wheat' in kwargs['initial']:
            line_count = kwargs['initial']['wheat'].count('\n')
            self.fields['wheat'].widget.attrs['rows'] = line_count + 1


class SelectProductionDayForm(Form):
    select_production_day = ModelChoiceField(queryset=ProductionDay.objects.all(), empty_label='Select production day')


class CustomerForm(ModelForm):
    first_name = CharField()
    last_name = CharField()

    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'point_of_sale', 'street', 'street_number', 'postal_code', 'city', 'telephone_number']


class ProductionDayMetaProductForm(forms.Form):
    meta_product = forms.CharField(widget=forms.HiddenInput, label='Source Product')
    meta_product_name = forms.CharField(disabled=True, required=False, label='Source Product')
    product = forms.ModelChoiceField(queryset=Product.objects.filter(category__name__iexact=settings.META_PRODUCT_CATEGORY_NAME), required=False, label='Target Product')

    def __init__(self, *args, **kwargs):
        self.production_day = kwargs.pop('production_day')
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(production_days__production_day=self.production_day)


ProductionDayMetaProductformSet = formset_factory(
    form=ProductionDayMetaProductForm, extra=0
)


class ProductionDayReminderForm(forms.Form):
    point_of_sale = forms.ModelChoiceField(empty_label='All', queryset=PointOfSale.objects.all(), required=False, label='Point of sale', help_text="Send emails to orders of specific point of sale, leave empty to send to all point of sales.")
    subject = forms.CharField(required=True)
    body = forms.CharField(required=True, widget=forms.Textarea)


class ReminderMessageForm(ModelForm):
    # messages = forms.ModelChoiceField(queryset=ReminderMessage.objects.none(), required=False, empty_label="Create new Message")
    point_of_sale = forms.ModelChoiceField(empty_label='All', queryset=PointOfSale.objects.all(), required=False, label='Point of sale')
    subject = forms.CharField(widget=forms.TextInput)
    production_day = forms.HiddenInput()

    class Meta:
        model = ReminderMessage
        fields = ['subject', 'body', 'point_of_sale', 'production_day']

    # def __init__(self, *args, **kwargs):
    #     production_day = kwargs.pop('production_day', None)
    #     super().__init__(*args, **kwargs)
    #     if production_day:
    #         self.fields['messages'].queryset = ReminderMessage.objects.filter(production_day=production_day)


class SelectReminderMessageForm(forms.Form):
    message = forms.ModelChoiceField(queryset=ReminderMessage.objects.none(), required=False, label='Create a new message or select a saved one', empty_label="Create a new message")

    def __init__(self, *args, **kwargs):
        production_day = kwargs.pop('production_day', None)
        super().__init__(*args, **kwargs)
        if production_day:
            self.fields['message'].queryset = ReminderMessage.objects.filter(production_day=production_day, state=ReminderMessage.State.PLANNED)
