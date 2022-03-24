from django.forms import ModelForm

from bakeup.workshop.models import Product


class ProductAddForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'image', 'categories', 'weight', 'weight_units', 'volume', 'volume_units', 'is_sellable', 'is_buyable', 'is_composable']