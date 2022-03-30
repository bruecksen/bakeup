from django import forms
from django.forms.formsets import BaseFormSet
from django.forms import formset_factory

from bakeup.workshop.models import Product


class CustomerOrderForm(forms.Form):
    production_day_id = forms.IntegerField()
    product_id = forms.IntegerField()
    quantity = forms.IntegerField()


CustomerOrderFormset = formset_factory(CustomerOrderForm, extra=0)