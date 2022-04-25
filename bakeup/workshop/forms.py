from django.forms import ModelChoiceField, ModelForm, Form

from bakeup.workshop.models import Product


class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'image', 'categories', 'weight', 'weight_units', 'volume', 'volume_units', 'is_sellable', 'is_buyable', 'is_composable']


class SelectProductForm(Form):
    product = ModelChoiceField(queryset=Product.objects.all())