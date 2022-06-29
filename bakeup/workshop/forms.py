from django.forms import DecimalField, FloatField, IntegerField, ModelChoiceField, ModelForm, Form
from bakeup.shop.models import ProductionDay

from bakeup.workshop.models import Product, ProductHierarchy, ProductionPlan


class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'image', 'category', 'weight', 'is_sellable', 'is_buyable', 'is_composable']


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
    dough_yield = IntegerField(min_value=100, label='TA')
    salt = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Salz')
    starter = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Starter')
    wheat = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Mehl')
    pre_ferment = DecimalField(decimal_places=2, min_value=0, max_value=100, label='Ferment. Mehlmenge')