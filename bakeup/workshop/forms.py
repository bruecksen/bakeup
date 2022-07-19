from django.forms import BooleanField, CharField, DecimalField, FloatField, IntegerField, ModelChoiceField, ModelForm, Form, formset_factory
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

AddProductFormSet = formset_factory(AddProductForm, extra=0)


class SelectProductForm(Form):
    product = ModelChoiceField(queryset=Product.objects.all())


class ProductHierarchyForm(Form):
    amount = FloatField()


class ProductionPlanDayForm(Form):
    production_day = ModelChoiceField(queryset=ProductionDay.objects.all())


class ProductionPlanForm(ModelForm):
    class Meta:
        model = ProductionPlan
        fields = ('start_date', 'duration')


class ProductKeyFiguresForm(Form):
    fermentation_loss = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Gärverlust')
    dough_yield = IntegerField(min_value=100, label='TA', disabled=True, required=False)
    salt = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Salz', disabled=True, required=False)
    starter = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Starter', disabled=True, required=False)
    wheat = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Mehl', disabled=True, required=False)
    pre_ferment = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Ferment. Mehlmenge', disabled=True, required=False)