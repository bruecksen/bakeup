from django.core.exceptions import ValidationError
from django import forms
from django.forms import formset_factory, modelformset_factory, BaseModelFormSet, BaseFormSet
from django.conf import settings
from django.utils.translation import gettext_lazy as _


from bakeup.users.models import User
from bakeup.shop.models import Customer, CustomerOrder, CustomerOrderPosition, ProductionDay, ProductionDayProduct

from bakeup.workshop.models import Product


class CustomerOrderForm(forms.Form):
    quantity = forms.IntegerField(label=_("Quantity"))

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
            raise forms.ValidationError(_("Sorry, but we don't have enough products."))
        if self.production_day_product.is_locked:
            raise forms.ValidationError(_("Sorry, but this production day is already locked."))

        return cleaned_data


class CustomerOrderBatchForm(forms.Form):
    product = forms.CharField(widget=forms.HiddenInput)
    quantity = forms.IntegerField(label=_("Quantity"))

    def __init__(self, *args, **kwargs):
        production_day_product = kwargs.pop('production_day_product')
        customer = kwargs.pop('customer')
        super().__init__(*args, **kwargs)
        if production_day_product.production_plan and production_day_product.production_plan.is_locked:
            self.fields['product'].disabled = True
            self.fields['quantity'].disabled = True
        self.fields['quantity'].widget.attrs.update({'min': 0, 'max': production_day_product.calculate_max_quantity()})
    

class CustomerProductionDayOrderForm(forms.Form):
    product_quantity = None
    next_url = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.production_day_products = kwargs.pop('production_day_products', None)
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        for production_day_product in self.production_day_products:
            if not production_day_product.is_locked and not production_day_product.is_sold_out:
                self.fields[f'production_day_{production_day_product.product.pk}-product'] = forms.IntegerField(widget=forms.HiddenInput, required=False)
                self.fields[f'production_day_{production_day_product.product.pk}-quantity'] = forms.IntegerField(label=_("Quantity"), required=False)
    
    def clean(self):
        cleaned_data = self.cleaned_data
        self.product_quantity = {}
        for production_day_product in self.production_day_products:
            if cleaned_data.get(f'production_day_{production_day_product.product.pk}-product'):
                product = cleaned_data[f'production_day_{production_day_product.product.pk}-product']
                quantity = cleaned_data[f'production_day_{production_day_product.product.pk}-quantity']
                if not product == production_day_product.product.pk:
                    raise forms.ValidationError(_("Wrong product"))
                if quantity > production_day_product.calculate_max_quantity(self.customer):
                    raise forms.ValidationError(_("Sorry, but we don't have enough products."))
                self.product_quantity[production_day_product.product] = quantity
        return cleaned_data


class ProductionDayForm(forms.ModelForm):
    class Meta:
        model = ProductionDay
        fields = ['day_of_sale', 'description']
        widgets = {
            'day_of_sale': forms.DateInput(format=('%Y-%m-%d'), attrs={'class':'form-control', 'placeholder':_('Select a date'), 'type':'date'}),
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


class BaseBatchCustomerOrderFormFormSet(BaseFormSet):
     def clean(self):
        """Checks that orders don't exceed max or quantity in production"""
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        if self.forms:
            production_day = self.forms[0].production_day
            products_qty = {}
            for product in production_day.production_day_products.all():
                products_qty['product_{}'.format(product.product.pk)] = {
                    'max_qty': product.max_quantity,
                    'ordered_qty': 0,
                    'is_locked': product.production_plan and product.production_plan.is_locked,
                }
            for form in self.forms:
                for product in products_qty.keys():
                    ordered_qty = form.cleaned_data.get(product)
                    if ordered_qty:
                        products_qty[product]['ordered_qty'] = products_qty[product]['ordered_qty'] + ordered_qty
            if any(v['is_locked'] and v['ordered_qty'] > v['max_qty'] for k, v in products_qty.items()):
                raise ValidationError(_("There are more products ordered then max qty."))

class BatchCustomerOrderForm(forms.Form):
    customer = forms.CharField(widget=forms.HiddenInput)
    customer_name = forms.CharField(disabled=True, required=False)

    def __init__(self, *args, **kwargs):
        self.production_day = kwargs.pop('production_day')
        super().__init__(*args, **kwargs)
        # self.fields['customer'].widget.attrs['disabled'] = True
        # self.fields['customer'].label_from_instance = lambda instance: "{} ({})".format(instance, instance.user.email)
        for product in self.production_day.production_day_products.all():
            field_name = 'product_{}'.format(product.product.pk)
            self.fields[field_name] = forms.IntegerField(required=False, label=_("{} (max. {})").format(product.product.name, product.max_quantity), widget=forms.NumberInput(attrs={'placeholder': _('Quantity')}))

    def get_product_fields(self):
        for field_name in self.fields:
            if field_name.startswith('product_'):
                yield self[field_name]


class BaseProductionDayProductFormSet(BaseModelFormSet):
     def clean(self):
        """Checks that no two articles have the same title."""
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return

        products = []
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            product = form.cleaned_data.get('product')
            if product in products:
                raise ValidationError(_("You can't add the same product twice!"))
            products.append(product)


ProductionDayProductFormSet = modelformset_factory(
    ProductionDayProduct, fields=("product", "max_quantity", "is_published", "group"), extra=1,  can_delete=True, formset=BaseProductionDayProductFormSet
)

CustomerOrderPositionFormSet = modelformset_factory(
    CustomerOrderPosition, form=CustomerOrderPositionForm, extra=0, can_delete=True
)

BatchCustomerOrderFormSet = formset_factory(
    form=BatchCustomerOrderForm, extra=0,  formset=BaseBatchCustomerOrderFormFormSet, 
)

class CustomerForm(forms.ModelForm):

    class Meta:
        model = Customer
        fields = ['point_of_sale']


class BatchCustomerOrderTemplateForm(forms.Form):
    customer = forms.CharField(widget=forms.HiddenInput)
    customer_name = forms.CharField(disabled=True, required=False)

    def __init__(self, *args, **kwargs):
        self.products = Product.objects.filter(is_recurring=True)
        super().__init__(*args, **kwargs)
        # self.fields['customer'].widget.attrs['disabled'] = True
        # self.fields['customer'].label_from_instance = lambda instance: "{} ({})".format(instance, instance.user.email)
        for product in self.products:
            field_name = 'product_{}'.format(product.pk)
            self.fields[field_name] = forms.IntegerField(required=False, label=product.name, widget=forms.NumberInput(attrs={'placeholder': _('Quantity')}))

    def get_product_fields(self):
        for field_name in self.fields:
            if field_name.startswith('product_'):
                yield self[field_name]


BatchCustomerOrderTemplateFormSet = formset_factory(
    form=BatchCustomerOrderTemplateForm, extra=0
)