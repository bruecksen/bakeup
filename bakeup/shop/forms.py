from django import forms
from django.forms.formsets import BaseFormSet
from django.forms import formset_factory

from bakeup.workshop.models import Product


class CustomerOrderForm(forms.Form):
    product = forms.CharField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(label="Quantity")

    def __init__(self, *args, **kwargs):
        production_day_product = kwargs.pop('production_day_product')
        super().__init__(*args, **kwargs)
        if not production_day_product.is_open_for_orders:
            self.fields['product'].disabled = True
            self.fields['quantity'].disabled = True


class CustomerProductionDayOrderForm(forms.Form):

    product_quantity = None

    def __init__(self, *args, **kwargs):
        self.production_day_products = kwargs.pop('production_day_products', None)
        super().__init__(*args, **kwargs)
        for production_day_product in self.production_day_products:
            self.fields[f'production_day_{production_day_product.product.pk}-product'] = forms.IntegerField(widget=forms.HiddenInput)
            self.fields[f'production_day_{production_day_product.product.pk}-quantity'] = forms.IntegerField(label="Quantity")

    def clean(self):
        cleaned_data = self.cleaned_data
        self.product_quantity = {}
        for production_day_product in self.production_day_products:
            product = cleaned_data[f'production_day_{production_day_product.product.pk}-product']
            quantity = cleaned_data[f'production_day_{production_day_product.product.pk}-quantity']
            if not product == production_day_product.product.pk:
                raise forms.ValidationError("Wrong product")
            if quantity > production_day_product.max_quantity:
                # TODO check for customer orders
                raise forms.ValidationError("Not enough products")
            self.product_quantity[production_day_product.product] = quantity
        return cleaned_data

    def get_product_quantity(self):
        return self.product_quantity


