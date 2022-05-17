from django import forms
from django.forms.formsets import BaseFormSet
from django.forms import formset_factory, modelformset_factory
from bakeup.shop.models import ProductionDay, ProductionDayProduct

from bakeup.workshop.models import Product


class CustomerOrderForm(forms.Form):
    product = forms.CharField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(label="Quantity")

    def __init__(self, *args, **kwargs):
        production_day_product = kwargs.pop('production_day_product')
        customer = kwargs.pop('customer')
        super().__init__(*args, **kwargs)
        if production_day_product.production_plan:
            self.fields['product'].disabled = True
            self.fields['quantity'].disabled = True
        self.fields['quantity'].widget.attrs.update({'min': 0, 'max': production_day_product.calculate_max_quantity(customer)})
    

class CustomerProductionDayOrderForm(forms.Form):

    product_quantity = None

    def __init__(self, *args, **kwargs):
        self.production_day_products = kwargs.pop('production_day_products', None)
        self.customer = kwargs.pop('customer', None)
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
            if quantity > production_day_product.calculate_max_quantity(self.customer):
                raise forms.ValidationError("Sorry, but we don't have enough products.")
            self.product_quantity[production_day_product.product] = quantity
        return cleaned_data

    def get_product_quantity(self):
        return self.product_quantity


class ProductionDayForm(forms.ModelForm):
    class Meta:
        model = ProductionDay
        fields = ['day_of_sale']
        widgets = {
            'day_of_sale': forms.DateInput(format=('%Y-%m-%d'), attrs={'class':'form-control', 'placeholder':'Select a date', 'type':'date'}),
        }


class ProductionDayProductForm(forms.ModelForm):

    class Meta:
        model = ProductionDayProduct
        fields = ['product', 'max_quantity']


ProductionDayProductFormSet = modelformset_factory(
    ProductionDayProduct, fields=("product", "max_quantity"), extra=1,  can_delete=False
)