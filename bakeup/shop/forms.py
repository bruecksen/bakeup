from django import forms
from django.forms.formsets import BaseFormSet
from django.forms import formset_factory, modelformset_factory
from bakeup.users.models import User
from bakeup.shop.models import Customer, CustomerOrder, CustomerOrderPosition, ProductionDay, ProductionDayProduct

from bakeup.workshop.models import Product


class CustomerOrderForm(forms.Form):
    quantity = forms.IntegerField(label="Quantity")

    def __init__(self, *args, **kwargs):
        self.production_day_product = kwargs.pop('production_day_product')
        self.product = self.production_day_product.product
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        if self.production_day_product.production_plan and self.production_day_product.production_plan.is_locked:
            self.fields['quantity'].disabled = True
        self.fields['quantity'].widget.attrs.update({'min': 0, 'max': self.production_day_product.calculate_max_quantity(self.customer)})

    def clean(self):
        cleaned_data = self.cleaned_data
        if int(cleaned_data['quantity']) > self.production_day_product.calculate_max_quantity(self.customer):
            raise forms.ValidationError("Sorry, but we don't have enough products.")
        if self.production_day_product.is_locked:
            raise forms.ValidationError("Sorry, aber es sind keine Bestellungen für diesen Tag möglich")

        return cleaned_data
    

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
        fields = ['day_of_sale', 'description']
        widgets = {
            'day_of_sale': forms.DateInput(format=('%Y-%m-%d'), attrs={'class':'form-control', 'placeholder':'Select a date', 'type':'date'}),
            'description': forms.Textarea(attrs={'rows':3}),
        }


class ProductionDayProductForm(forms.ModelForm):

    class Meta:
        model = ProductionDayProduct
        fields = ['product', 'max_quantity', 'is_published']


class CustomerOrderPositionForm(forms.ModelForm):

    class Meta:
        model = CustomerOrderPosition
        fields = ['product', 'quantity']

    def __init__(self, *args, **kwargs):
        self.production_day_products = kwargs.pop('production_day_products', Product.objects.all())
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = self.production_day_products


class BatchCustomerOrderForm(forms.Form):
    customer = forms.CharField(widget=forms.HiddenInput)
    customer_name = forms.CharField(disabled=True, required=False)

    def __init__(self, *args, **kwargs):
        self.production_day = kwargs.pop('production_day')
        self.production_day_products = Product.objects.filter(production_days__production_day=self.production_day)
        super().__init__(*args, **kwargs)
        # self.fields['customer'].widget.attrs['disabled'] = True
        # self.fields['customer'].label_from_instance = lambda instance: "{} ({})".format(instance, instance.user.email)
        for product in self.production_day_products:
            field_name = 'product_{}'.format(product.pk)
            self.fields[field_name] = forms.IntegerField(required=False, label=product.name, widget=forms.NumberInput(attrs={'placeholder': 'Quantity'}))

    def get_product_fields(self):
        for field_name in self.fields:
            if field_name.startswith('product_'):
                yield self[field_name]


ProductionDayProductFormSet = modelformset_factory(
    ProductionDayProduct, fields=("product", "max_quantity", "is_published"), extra=1,  can_delete=True
)

CustomerOrderPositionFormSet = modelformset_factory(
    CustomerOrderPosition, form=CustomerOrderPositionForm, extra=0, can_delete=True
)

BatchCustomerOrderFormSet = formset_factory(
    form=BatchCustomerOrderForm, extra=0
)

class CustomerForm(forms.ModelForm):

    class Meta:
        model = Customer
        fields = ['point_of_sale']