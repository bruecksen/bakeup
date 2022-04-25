from django.forms import FloatField, IntegerField, ModelChoiceField, ModelForm, Form
from bakeup.shop.models import ProductionDay

from bakeup.workshop.models import Product, ProductHierarchy


class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'image', 'categories', 'weight', 'weight_units', 'volume', 'volume_units', 'is_sellable', 'is_buyable', 'is_composable']


class SelectProductForm(Form):
    product = ModelChoiceField(queryset=Product.objects.all())


class ProductHierarchyForm(Form):
    amount = FloatField()


class ProductionPlanForm(Form):
    production_day = ModelChoiceField(queryset=ProductionDay.objects.all())