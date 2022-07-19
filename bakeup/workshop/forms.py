from unicodedata import category
from django.forms import BooleanField, CharField, DecimalField, FloatField, IntegerField, ModelChoiceField, ModelForm, Form, Textarea, formset_factory
from django.db.models import Q

from bakeup.shop.models import ProductionDay

from bakeup.workshop.models import Category, Product, ProductHierarchy, ProductionPlan


class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'image', 'category', 'weight', 'is_sellable', 'is_buyable', 'is_composable']


class AddProductForm(Form):
    weight = FloatField(required=True)
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
    production_day = ModelChoiceField(queryset=ProductionDay.objects.filter(production_plans=None))


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